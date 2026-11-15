"""Build static site: python -m tracker.build_site --db data/tracker.db --out dist"""
from __future__ import annotations
import argparse, json, math, os, shutil, time
from . import db as dbm

WINDOW = 7 * 86400
DEFAULT_P = 0.10          # assumed hourly-ish interruption risk when a source publishes nothing


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
    state = {r[0]: r[1] for r in db.execute("SELECT provider,n FROM provider_state")}
    rows = []
    q = "SELECT key,source,provider,gpu,region,gpu_count,price,p_int,reliability,note,first_prun,last_prun,seen,last_ts FROM offers"
    for (key, src, prov, gpu, reg, cnt, price, p_int, rel, note, first, last, seen, ts) in db.execute(q):
        if last != state.get(src):      # not in the source's latest successful poll
            continue
        hist = db.execute("SELECT ts,price FROM history WHERE key=? ORDER BY ts", (key,)).fetchall()
        cv = vol(hist, now)
        p = p_int if p_int is not None else DEFAULT_P
        adj = price / (1 - min(p, 0.9)) * (1 + (cv or 0))
        if p_int is None: tier = "?"
        elif p_int <= 0.05 and (cv or 0) < 0.10: tier = "A"
        elif p_int <= 0.15 and (cv or 0) < 0.30: tier = "B"
        else: tier = "C"
        rows.append(dict(
            key=key, provider=prov, gpu=gpu, region=reg, gpu_count=cnt, price=round(price, 4),
            adj_price=round(adj, 4), tier=tier, p_int=p_int, reliability=rel, vol7d=None if cv is None else round(cv, 3),
            in_stock_pct=round(100 * seen / max(1, state[src] - first + 1)), note=note,
            history=[[t, round(pr, 4)] for t, pr in hist[-60:]]))
    rows.sort(key=lambda r: r["adj_price"])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/tracker.db"); ap.add_argument("--out", default="dist")
    a = ap.parse_args()
    now = int(time.time())
    db = dbm.connect(a.db)
    rows = build_rows(db, now)
    shutil.rmtree(a.out, ignore_errors=True)
    shutil.copytree("site", a.out)
    # Single data file. The whole site MUST sit behind Cloudflare Access (owner-only).
    json.dump({"meta": {"generated_at": now}, "rows": rows}, open(os.path.join(a.out, "data.json"), "w"))
    print(f"{len(rows)} rows -> {a.out}")


if __name__ == "__main__":
    main()
