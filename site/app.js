// Shared table renderer. Page sets window.DATA_URL and window.ANALYTICS.
const $ = (s) => document.querySelector(s);
let rows = [], sort = { k: "adj_price", asc: true };
const fmt = (x, d = 3) => (x == null ? "–" : Number(x).toFixed(d));
const spark = (h) => {
  if (!h || h.length < 2) return "";
  const v = h.map((p) => p[1]), lo = Math.min(...v), hi = Math.max(...v), w = 80, ht = 20;
  const pts = v.map((y, i) => `${(i / (v.length - 1)) * w},${ht - ((y - lo) / (hi - lo || 1)) * (ht - 2) - 1}`).join(" ");
  return `<svg width="${w}" height="${ht}"><polyline fill="none" stroke="currentColor" stroke-width="1.5" points="${pts}"/></svg>`;
};
function render() {
  const g = $("#gpu").value, q = $("#q").value.toLowerCase();
  let r = rows.filter((x) => (!g || x.gpu === g) && (!q || (x.provider + x.gpu + x.region).toLowerCase().includes(q)));
  r.sort((a, b) => ((a[sort.k] ?? 1e9) > (b[sort.k] ?? 1e9) ? 1 : -1) * (sort.asc ? 1 : -1));
  const cols = [["provider", "Provider"], ["gpu", "GPU"], ["region", "Region"], ["price", "$/GPU-hr"], ["adj_price", "Stability-adj $/hr"],
    ["tier", "Stability"], ["in_stock_pct", "In stock %"], ["vol7d", "7d volatility"]];
  if (window.ANALYTICS) cols.push(["history", "Price history"]);
  $("#thead").innerHTML = cols.map(([k, n]) => `<th data-k="${k}">${n}</th>`).join("");
  $("#tbody").innerHTML = r.map((x) => `<tr><td>${x.provider}</td><td>${x.gpu}${x.gpu_count > 1 ? ` <small>×${x.gpu_count}</small>` : ""}</td><td>${x.region}</td>
    <td>${fmt(x.price)}</td><td>${fmt(x.adj_price)}</td><td title="${x.note || ""}"><span class="t t${x.tier === "?" ? "u" : x.tier}">${x.tier}</span></td>
    <td>${x.in_stock_pct}</td><td>${x.vol7d == null ? "new" : (x.vol7d * 100).toFixed(1) + "%"}</td>${window.ANALYTICS ? `<td>${spark(x.history)}</td>` : ""}</tr>`).join("");
  document.querySelectorAll("th").forEach((th) => (th.onclick = () => { sort = { k: th.dataset.k, asc: sort.k === th.dataset.k ? !sort.asc : true }; render(); }));
}
fetch(window.DATA_URL).then((r) => r.json()).then((d) => {
  rows = d.rows;
  $("#gpu").innerHTML = '<option value="">All GPUs</option>' + [...new Set(rows.map((x) => x.gpu))].sort().map((g) => `<option>${g}</option>`).join("");
  $("#updated").textContent = "Updated " + new Date(d.meta.generated_at * 1000).toLocaleString();
  $("#gpu").onchange = $("#q").oninput = render; render();
}).catch(() => ($("#updated").textContent = "Failed to load data"));
