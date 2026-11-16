const $ = (s) => document.querySelector(s);
const PROFILES = {
  llm: { name: "Full fine-tune / RL of a 4B LLM (hybrid_reasoning)", vram: 80, bf16: true, ngpu: 1, job: 40,
    note: "From your logs: 4B full SFT peaks at 66–90 GB (needs an 80 GB+ card), bf16, ~7,300 tok/s on an H100 (RTX PRO 6000 ≈ 4,400). Your GRPO text run was ~39 H100-hours; the VMs get preempted often and restarting has failed (capacity), so lost-work hours matter." },
  small: { name: "Small-model experiments / debugging (≥ 24 GB)", vram: 24, bf16: true, ngpu: 1, job: 10,
    note: "Short runs, ≥ 24 GB, bf16. Good place for L4 / L40S / RTX 4090-class cards." },
  raw: { name: "Cheapest compute per dollar (any card)", vram: 0, bf16: false, ngpu: 1, job: 40,
    note: "Ignores VRAM and bf16; ranks only by price ÷ estimated speed." },
};
const COLS = [
  ["provider", "Provider", "cat"], ["gpu", "GPU", "cat"], ["region", "Region", "cat"], ["gpu_count", "GPUs/rental", "num"],
  ["price", "$/GPU-hr", "num", 3], ["vram_gb", "VRAM GB", "num", 0], ["speed", "Speed ×H100", "num", 2],
  ["mtbf", "Hours between interruptions", "num", 0], ["tier", "Tier", "cat"], ["reliability", "Host reliab.", "num", 3],
  ["in_stock_pct", "In stock %", "num", 0], ["vol7d", "7d price vol.", "num", 2],
  ["effPrice", "Eff. $/GPU-hr", "num", 3], ["perH100", "$ per H100-hour of work", "num", 3], ["jobCost", "Est. job cost $", "num", 0],
  ["history", "History", "spark"],
];
let rows = [], NOW = 0, hidden = new Set(), openKeys = new Set(), specs = {}, sort = { k: "jobCost", asc: true }, sel = {}, rng = {};

const num = (id) => parseFloat($(id).value) || 0;
const fmt = (v, d = 3) => (v == null || Number.isNaN(v) || !Number.isFinite(v) ? "–" : Number(v).toFixed(d));
function compute(r) {
  const unk = num("#unk") / 24, L = num("#lost"), N = Math.max(1, num("#ngpu")), job = num("#job");
  const lam = r.int_per_hr ?? unk, f = Math.min(lam * L, 0.9);
  const mult = r.gpu_count > N ? r.gpu_count / N : 1; // billed for the whole shape
  const effPrice = (r.price * mult) / (1 - f);
  const perH100 = r.speed ? effPrice / r.speed : null;
  r.mtbf = lam > 0 ? 1 / lam : null;
  r.tier = r.int_per_hr == null ? "?" : r.mtbf >= 200 ? "A" : r.mtbf >= 20 ? "B" : "C";
  r.effPrice = effPrice;
  r.perH100 = perH100;
  r.jobCost = perH100 == null ? null : perH100 * job;
  r.wall = r.speed ? job / (r.speed * N) / (1 - f) : null;
  r.nint = r.wall == null ? null : r.wall * lam;
}
const spark = (h) => {
  if (!h || h.length < 2) return "";
  const v = h.map((p) => p[1]), lo = Math.min(...v), hi = Math.max(...v), w = 70, ht = 18;
  return `<svg width="${w}" height="${ht}"><polyline fill="none" stroke="currentColor" stroke-width="1.5" points="${v.map((y, i) => `${(i / (v.length - 1)) * w},${ht - ((y - lo) / (hi - lo || 1)) * (ht - 2) - 1}`).join(" ")}"/></svg>`;
};
function passes(r) {
  for (const [k, , t] of COLS) {
    if (t === "cat" && sel[k]?.size && !sel[k].has(String(r[k]))) return false;
    if (t === "num" && rng[k]) {
      const [lo, hi] = rng[k], v = r[k];
      if ((lo != null || hi != null) && v == null) return false;
      if (lo != null && v < lo) return false;
      if (hi != null && v > hi) return false;
    }
  }
  const q = $("#q").value.toLowerCase();
  return !q || `${r.provider} ${r.gpu} ${r.region} ${r.note}`.toLowerCase().includes(q);
}
const tierSpan = (t, note) => `<span class="t t${t === "?" ? "u" : t}" title="${(note || "").replace(/"/g, "'")}">${t}</span>`;

function render() {
  specs = {};
  rows.forEach(compute);
  const vis = rows.filter(passes);
  vis.sort((a, b) => {
    const x = a[sort.k], y = b[sort.k];
    if (x == null) return 1;
    if (y == null) return -1;
    return (x > y ? 1 : x < y ? -1 : 0) * (sort.asc ? 1 : -1);
  });
  $("#count").textContent = `${vis.length} of ${rows.length} offers`;
  $("#tbody").innerHTML = vis.slice(0, 1500).map((r) => `<tr data-key="${r.key.replace(/"/g, "&quot;")}" class="${openKeys.has(r.key) ? "open" : ""}">` + COLS.map(([k, , t, d]) =>
    k === "tier" ? `<td>${tierSpan(r.tier, r.note)}</td>` : t === "spark" ? `<td>${spark(r.history)}</td>`
      : t === "num" ? `<td>${fmt(r[k], d)}${k === "vol7d" && r.vol7d == null ? "new" : ""}</td>` : `<td>${r[k]}</td>`).join("") + "</tr>" + (openKeys.has(r.key) ? detailRow(r) : "")).join("");
  renderPicks(vis);
  renderHist(vis);
}
// ---------- price-history charts ----------
const PROV = ["gcp", "aws", "azure", "vast", "lium", "nebius", "primeintellect"];
const pcol = (p) => (PROV.includes(p) ? `var(--s${PROV.indexOf(p) + 1})` : "var(--u)");
const valueAt = (pts, t) => { let v = null; for (const [pt, pp] of pts) { if (pt <= t) v = pp; else break; } return v; };
const ago = (s) => (s < 90 ? "now" : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 129600 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`);
const usd = (v) => "$" + (v < 1 ? v.toFixed(3) : v.toFixed(2));
// cheapest price over time across several offers (each history = price steps; an offer counts from its first point)
function mergeMin(hists) {
  const ts = [...new Set(hists.flatMap((h) => h.map((p) => p[0])))].sort((a, b) => a - b), out = [];
  for (const t of ts) {
    const vs = hists.map((h) => valueAt(h, t)).filter((v) => v != null), m = Math.min(...vs);
    if (!out.length || out[out.length - 1][1] !== m) out.push([t, m]);
  }
  return out;
}
function chartSvg(id, series, t0, t1, big) {
  const W = big ? 640 : 300, H = big ? 190 : 105, L = 40, R = 6, T = 6, B = 16;
  const clip = series.map((s) => {
    const first = valueAt(s.pts, t0) ?? s.pts[0][1];
    const inner = s.pts.filter((p) => p[0] > t0 && p[0] <= t1);
    return { ...s, c: [[Math.max(t0, s.pts[0][0] > t0 ? s.pts[0][0] : t0), first], ...inner] };
  });
  const vs = clip.flatMap((s) => s.c.map((p) => p[1]));
  let lo = Math.min(...vs), hi = Math.max(...vs);
  if (hi - lo < hi * 0.02) { lo *= 0.95; hi *= 1.05; } else { const pad = (hi - lo) * 0.1; lo -= pad; hi += pad; }
  const X = (t) => L + ((t - t0) / (t1 - t0 || 1)) * (W - L - R), Y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  specs[id] = { series: clip, t0, t1, X, Y, L, W, R, T, H, B };
  const grid = [0, 0.5, 1].map((f) => { const v = lo + f * (hi - lo); return `<line class="gl" x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${L - 4}" y="${Y(v) + 3}" text-anchor="end">${usd(v)}</text>`; }).join("");
  const lines = clip.map((s) => {
    let d = `M${X(s.c[0][0])},${Y(s.c[0][1])}`;
    for (let i = 1; i < s.c.length; i++) d += `H${X(s.c[i][0])}V${Y(s.c[i][1])}`;
    d += `H${X(t1)}`;
    return `<path class="ln" stroke="${s.color}" d="${d}"/>`;
  }).join("");
  return `<svg class="ch" data-id="${id}" viewBox="0 0 ${W} ${H}">${grid}<text x="${L}" y="${H - 3}">${ago(NOW - t0)}</text><text x="${W - R}" y="${H - 3}" text-anchor="end">now</text>${lines}<g class="hv" style="display:none"><line class="xh" y1="${T}" y2="${H - B}"/>${clip.map((s) => `<circle r="3.5" fill="${s.color}" stroke="var(--bg)" stroke-width="2" data-n="${s.name}"/>`).join("")}</g></svg>`;
}
function renderHist(vis) {
  const lg = $("#hlegend"), present = PROV.filter((p) => vis.some((r) => r.provider === p));
  lg.innerHTML = present.map((p) => `<span class="chip ${hidden.has(p) ? "off" : ""}" data-p="${p}" style="--c:${pcol(p)}"><i></i>${p}</span>`).join("");
  const minv = num("#minvram"), all = vis.filter((r) => r.history?.length && !hidden.has(r.provider) && (r.vram_gb ?? 0) >= minv);
  const dmin = Math.min(...all.map((r) => r.history[0][0]), NOW), rg = num("#hrange");
  const t0 = rg ? Math.max(NOW - rg, dmin) : dmin;
  const byGpu = new Map();
  for (const r of all) { if (!byGpu.has(r.gpu)) byGpu.set(r.gpu, new Map()); const m = byGpu.get(r.gpu); if (!m.has(r.provider)) m.set(r.provider, []); m.get(r.provider).push(r.history); }
  const panels = [...byGpu].map(([gpu, m]) => {
    const series = [...m].map(([prov, hs]) => ({ name: prov, color: pcol(prov), pts: mergeMin(hs) })).sort((a, b) => PROV.indexOf(a.name) - PROV.indexOf(b.name));
    const move = Math.max(...series.map((s) => { const v = s.pts.filter((p) => p[0] >= t0).map((p) => p[1]).concat(valueAt(s.pts, t0) ?? []); return (Math.max(...v) - Math.min(...v)) / Math.min(...v); }));
    return { gpu, series, move, cur: Math.min(...series.map((s) => s.pts[s.pts.length - 1][1])) };
  });
  const ord = $("#horder").value;
  panels.sort((a, b) => ord === "name" ? a.gpu.localeCompare(b.gpu) : ord === "cheap" ? a.cur - b.cur : b.move - a.move || a.cur - b.cur);
  const n = +$("#hn").value;
  $("#hgrid").innerHTML = panels.slice(0, n).map((p, i) => {
    const mv = p.move > 0.0005 ? `${p.move >= 0.1 ? Math.round(p.move * 100) : (p.move * 100).toFixed(1)}% swing` : "flat";
    return `<div class="panel"><h3>${p.gpu} <small>from ${usd(p.cur)} · ${mv}</small></h3>${chartSvg("g" + i, p.series, t0, NOW, false)}</div>`;
  }).join("") + (panels.length > n ? `<p class="hint">${panels.length - n} more GPUs hidden — change “Show”.</p>` : "") + (panels.length ? "" : "<p class='hint'>No history for the current filters.</p>");
}
function detailRow(r) {
  const h = r.history || [];
  if (!h.length) return "";
  const t0 = Math.min(h[0][0], NOW - 3600);
  return `<tr class="detail"><td colspan="${COLS.length}"><b>${r.provider} ${r.gpu} ×${r.gpu_count} · ${r.region}</b> <small>${h.length} price change${h.length > 1 ? "s" : ""} recorded</small><br>${chartSvg("d" + r.key, [{ name: r.provider, color: pcol(r.provider), pts: h }], t0, NOW, true)}</td></tr>`;
}
const tip = () => $("#tip");
document.addEventListener("mousemove", (e) => {
  const svg = e.target.closest?.("svg.ch"), t = tip();
  if (!svg) { t.style.display = "none"; document.querySelectorAll(".hv").forEach((g) => (g.style.display = "none")); return; }
  const sp = specs[svg.dataset.id]; if (!sp) return;
  const box = svg.getBoundingClientRect(), x = ((e.clientX - box.left) / box.width) * sp.W;
  const tm = sp.t0 + Math.min(1, Math.max(0, (x - sp.L) / (sp.W - sp.L - sp.R))) * (sp.t1 - sp.t0);
  const vals = sp.series.map((s) => ({ s, v: valueAt(s.c, tm) })).filter((o) => o.v != null).sort((a, b) => a.v - b.v);
  const g = svg.querySelector(".hv"); g.style.display = "";
  const px = sp.L + ((tm - sp.t0) / (sp.t1 - sp.t0 || 1)) * (sp.W - sp.L - sp.R);
  g.querySelector("line").setAttribute("x1", px); g.querySelector("line").setAttribute("x2", px);
  g.querySelectorAll("circle").forEach((c) => { const o = vals.find((o) => o.s.name === c.dataset.n); c.style.display = o ? "" : "none"; if (o) { c.setAttribute("cx", px); c.setAttribute("cy", sp.Y(o.v)); } });
  t.innerHTML = `<b>${tm >= NOW - 90 ? "now" : new Date(tm * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</b>` + vals.map((o) => `<div><i style="background:${o.s.color}"></i>${o.s.name} ${usd(o.v)}</div>`).join("");
  t.style.display = "block";
  t.style.left = Math.min(e.clientX + 14, innerWidth - t.offsetWidth - 8) + "px"; t.style.top = Math.min(e.clientY + 14, innerHeight - t.offsetHeight - 8) + "px";
});
document.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (chip) { hidden.has(chip.dataset.p) ? hidden.delete(chip.dataset.p) : hidden.add(chip.dataset.p); render(); return; }
  const tr = e.target.closest("#tbody tr[data-key]");
  if (tr && !e.target.closest("a")) { const k = tr.dataset.key; openKeys.has(k) ? openKeys.delete(k) : openKeys.add(k); render(); }
});

function renderPicks(vis) {
  const minv = num("#minvram"), bf = $("#needbf16").checked;
  const ok = vis.filter((r) => r.speed && r.jobCost != null && (r.vram_gb ?? 0) >= minv && (!bf || r.bf16));
  const best = new Map();
  for (const r of ok.sort((a, b) => a.jobCost - b.jobCost)) { const k = r.provider + r.gpu; if (!best.has(k)) best.set(k, r); }
  const top = [...best.values()].slice(0, 8);
  const stable = top.find((r) => r.tier === "A" || r.tier === "B");
  const head = "<tr>" + ["", "Provider", "GPU", "Region", "$/GPU-hr", "Speed ×H100", "Tier", "Est. hours", "Est. interruptions", "Est. job cost"].map((h) => `<th>${h}</th>`).join("") + "</tr>";
  $("#picks").innerHTML = top.length ? head + top.map((r, i) => `<tr class="${r === top[0] ? "best" : ""}"><td>${r === top[0] ? "Cheapest" : r === stable ? "Cheapest stable" : i + 1}</td><td>${r.provider}${(r.note || '').startsWith('GCP GPU SKU') ? ' <span title="GCP GPU SKU price: may exclude the host VM cost">⚠</span>' : ''}</td><td>${r.gpu}${r.gpu_count > 1 ? ` ×${r.gpu_count}` : ""}</td><td>${r.region}</td><td>${fmt(r.price)}</td><td>${fmt(r.speed, 2)}${r.measured ? "" : "*"}</td><td>${tierSpan(r.tier, r.note)}</td><td>${fmt(r.wall, 1)}</td><td>${fmt(r.nint, 1)}</td><td><b>$${fmt(r.jobCost, 0)}</b></td></tr>`).join("")
    : "<tr><td>No offers match these requirements and filters.</td></tr>";
}
function buildHeader() {
  $("#thead").innerHTML = "<tr>" + COLS.map(([k, n, t]) => `<th class="${t === "spark" ? "" : "s"}" data-k="${k}">${n}</th>`).join("") + '</tr><tr class="f">' + COLS.map(([k]) => `<th id="f_${k}"></th>`).join("") + "</tr>";
  document.querySelectorAll("th.s").forEach((th) => (th.onclick = () => { sort = { k: th.dataset.k, asc: sort.k === th.dataset.k ? !sort.asc : true }; render(); }));
  for (const [k, , t] of COLS) {
    const cell = $("#f_" + k);
    if (t === "num") {
      cell.innerHTML = '<div class="mm"><input placeholder="min"><input placeholder="max"></div>';
      const [a, b] = cell.querySelectorAll("input");
      const upd = () => { const lo = a.value === "" ? null : +a.value, hi = b.value === "" ? null : +b.value; rng[k] = lo == null && hi == null ? null : [lo, hi]; render(); };
      a.oninput = b.oninput = upd;
    } else if (t === "cat") {
      const vals = k === "tier" ? ["A", "B", "C", "?"] : [...new Set(rows.map((r) => String(r[k])))].sort();
      sel[k] = new Set();
      cell.innerHTML = `<details class="ms"><summary>All</summary><div class="menu">${vals.map((v) => `<label><input type="checkbox" value="${v.replace(/"/g, "&quot;")}"> ${v}</label>`).join("")}</div></details>`;
      const sum = cell.querySelector("summary");
      cell.querySelectorAll("input").forEach((cb) => (cb.onchange = () => {
        cb.checked ? sel[k].add(cb.value) : sel[k].delete(cb.value);
        sum.textContent = sel[k].size ? `${sel[k].size} selected` : "All";
        render();
      }));
    }
  }
}
function applyProfile() {
  const p = PROFILES[$("#profile").value];
  $("#minvram").value = p.vram; $("#needbf16").checked = p.bf16; $("#ngpu").value = p.ngpu; $("#job").value = p.job;
  $("#profnote").textContent = p.note;
  render();
}
fetch(window.DATA_URL).then((r) => r.json()).then((d) => {
  rows = d.rows; NOW = d.meta.generated_at;
  $("#updated").textContent = "Updated " + new Date(d.meta.generated_at * 1000).toLocaleString();
  $("#profile").innerHTML = Object.entries(PROFILES).map(([k, p]) => `<option value="${k}">${p.name}</option>`).join("");
  buildHeader();
  $("#profile").onchange = applyProfile;
  ["#hrange", "#horder", "#hn", "#ngpu", "#job", "#minvram", "#needbf16", "#lost", "#unk", "#q"].forEach((s) => ($(s).oninput = render));
  $("#reset").onclick = () => { sel = {}; rng = {}; $("#q").value = ""; buildHeader(); render(); };
  applyProfile();
}).catch((e) => { $("#updated").textContent = "Failed to load data: " + e; });

fetch("/cpu.json").then((r) => r.json()).then((cpu) => {
  const draw = () => {
    const m = num("#cpumin"), pv = $("#cpuprov").value.toLowerCase();
    const r = cpu.filter((x) => x.vcpus >= m && (!pv || x.provider.includes(pv))).slice(0, 12);
    $("#cputbl").innerHTML = "<tr>" + ["Provider", "Instance", "Region", "vCPUs", "RAM GB", "$/hr", "$/vCPU-hr"].map((h) => `<th>${h}</th>`).join("") + "</tr>" +
      r.map((x) => `<tr><td>${x.provider}</td><td>${x.instance}</td><td>${x.region}</td><td>${x.vcpus}</td><td>${fmt(x.mem_gb, 0)}</td><td>${fmt(x.price)}</td><td>${fmt(x.per_vcpu, 4)}</td></tr>`).join("");
  };
  $("#cpumin").oninput = $("#cpuprov").oninput = draw; draw();
}).catch(() => {});
