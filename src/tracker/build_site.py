"""Build static site: python -m tracker.build_site --db data/tracker.db --out dist"""
from __future__ import annotations
import argparse, json, math, os, shutil, time
from . import db as dbm
from .gpu_specs import spec_for

WINDOW = 7 * 86400


def vol(points, now):
    """Time-weighted coefficient of variation of price over the last 7 days (None if <1 day of data)."""
    pts = [(t, p) for t, p in points if t >= now - WINDOW]
    prior = [p for t, p in points if t < now - WINDOW]
    if prior:
        pts.insert(0, (now - WINDOW, prior[-1]))
    if not pts or now - pts[0][0] < 86400:
        return None
    ws, mean, var = [], 0.0, 0.0
    for i, (t, p) in enumerate(pts):
        ws.append(((pts[i + 1][0] if i + 1 < len(pts) else now) - t, p))
    tot = sum(w for w, _ in ws) or 1
    mean = sum(w * p for w, p in ws) / tot
    var = sum(w * (p - mean) ** 2 for w, p in ws) / tot
    return math.sqrt(var) / mean if mean else None


def build_rows(db, now):
    """One row per live offer with specs attached. Ranking/recommendation is done in the browser
    (site/app.js) so the owner can change the workload assumptions without a rebuild."""
    state = {r[0]: r[1] for r in db.execute("SELECT provider,n FROM provider_state")}
    gcp = {(g, c, rg): (a, rc, vp) for g, c, rg, a, rc, vp in db.execute("SELECT gpu,gpu_count,region,avg_rate,recent_rate,vm_price FROM gcp_preempt")}
    rows = []
    q = "SELECT key,source,provider,gpu,region,gpu_count,price,p_int,reliability,note,first_prun,last_prun,seen FROM offers"
    for (key, src, prov, gpu, reg, cnt, price, p_int, rel, note, first, last, seen) in db.execute(q):
        if last != state.get(src):      # not in the source's latest successful poll
            continue
        hist = db.execute("SELECT ts,price FROM history WHERE key=? ORDER BY ts", (key,)).fetchall()
        cv = vol(hist, now)
        spec = spec_for(gpu) or {}
        pre = gcp.get((gpu, cnt, reg)) if prov == "gcp" else None
        if pre:
            rel = 1 - pre[0]
            note = f"{note} | GCP 30d preemption rate {pre[0]:.1%} (last 7d {pre[1]:.1%})"
            if pre[2]:   # whole-VM price from Compute capacityHistory beats the GPU-SKU-only catalog price
                price, note = pre[2] / cnt, "GCP whole-VM spot list price (Compute API)" + note[note.index(" | "):]
        rows.append(dict(
            key=key, provider=prov, gpu=gpu, region=reg, gpu_count=cnt, price=round(price, 4),
            int_per_hr=p_int, reliability=rel, vol7d=None if cv is None else round(cv, 3),
            in_stock_pct=round(100 * seen / max(1, state[src] - first + 1)), note=note,
            vram_gb=spec.get("vram_gb"), tflops=spec.get("tflops"), bf16=spec.get("bf16"),
            speed=spec.get("speed"), tok_s=spec.get("tok_s"), measured=spec.get("measured"),
            history=[[t, round(pr, 4)] for t, pr in hist[-300:]]))
    rows.sort(key=lambda r: r["price"])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/tracker.db"); ap.add_argument("--out", default="dist")
    a = ap.parse_args()
    now = int(time.time())
    db = dbm.connect(a.db)
    rows = build_rows(db, now)
    shutil.copytree("site", a.out, dirs_exist_ok=True)  # overwrite in place; CI starts from a clean checkout
    # Single data file. The whole site MUST sit behind Cloudflare Access (owner-only).
    json.dump({"meta": {"generated_at": now}, "rows": rows}, open(os.path.join(a.out, "data.json"), "w"))
    cpu = [dict(zip(("provider", "instance", "region", "vcpus", "mem_gb", "price", "per_vcpu"), r))
           for r in db.execute("SELECT provider,instance,region,vcpus,mem_gb,price,per_vcpu FROM cpu_offers ORDER BY per_vcpu")]
    json.dump(cpu, open(os.path.join(a.out, "cpu.json"), "w"))
    print(f"{len(rows)} rows, {len(cpu)} cpu instances -> {a.out}")


if __name__ == "__main__":
    main()
