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
let rows = [], sort = { k: "jobCost", asc: true }, sel = {}, rng = {};

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
  rows.forEach(compute);
  const vis = rows.filter(passes);
  vis.sort((a, b) => {
    const x = a[sort.k], y = b[sort.k];
    if (x == null) return 1;
    if (y == null) return -1;
    return (x > y ? 1 : x < y ? -1 : 0) * (sort.asc ? 1 : -1);
  });
  $("#count").textContent = `${vis.length} of ${rows.length} offers`;
  $("#tbody").innerHTML = vis.slice(0, 1500).map((r) => "<tr>" + COLS.map(([k, , t, d]) =>
    k === "tier" ? `<td>${tierSpan(r.tier, r.note)}</td>` : t === "spark" ? `<td>${spark(r.history)}</td>`
      : t === "num" ? `<td>${fmt(r[k], d)}${k === "vol7d" && r.vol7d == null ? "new" : ""}</td>` : `<td>${r[k]}</td>`).join("") + "</tr>").join("");
  renderPicks(vis);
}
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
  rows = d.rows;
  $("#updated").textContent = "Updated " + new Date(d.meta.generated_at * 1000).toLocaleString();
  $("#profile").innerHTML = Object.entries(PROFILES).map(([k, p]) => `<option value="${k}">${p.name}</option>`).join("");
  buildHeader();
  $("#profile").onchange = applyProfile;
  ["#ngpu", "#job", "#minvram", "#needbf16", "#lost", "#unk", "#q"].forEach((s) => ($(s).oninput = render));
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
