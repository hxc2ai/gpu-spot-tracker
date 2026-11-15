"""Query the tracker from a terminal (or Claude Code).

  uv run python -m tracker.query --pull --gpu H100 --gpu "RTX PRO 6000" --min-vram 80 --job 40 --limit 15
  uv run python -m tracker.query --cpu --min-vcpus 32

--pull downloads the latest DB from the private B2 bucket (needs B2_* env vars from ~/.env).
Cost model matches site/app.js: eff = price * (billed shape / gpus used) / (1 - lam*lost); cost = job * eff / speed.
"""
from __future__ import annotations
import argparse, os, time
from . import db as dbm
from .build_site import build_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/tracker.db"); ap.add_argument("--pull", action="store_true")
    ap.add_argument("--gpu", action="append", help="GPU name substring, repeatable (OR)")
    ap.add_argument("--provider", action="append"); ap.add_argument("--min-vram", type=float, default=0)
    ap.add_argument("--bf16", action="store_true"); ap.add_argument("--ngpu", type=int, default=1)
    ap.add_argument("--job", type=float, default=40, help="job size in H100-hours")
    ap.add_argument("--lost", type=float, default=0.75, help="hours lost per interruption")
    ap.add_argument("--unknown-per-day", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=20); ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--min-vcpus", type=float, default=16)
    a = ap.parse_args()
    if a.pull:
        from . import b2
        os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
        print("pulled" if b2.pull(a.db) else "no DB in B2")
    db = dbm.connect(a.db)
    if a.cpu:
        for r in db.execute("SELECT provider,instance,region,vcpus,mem_gb,price,per_vcpu FROM cpu_offers WHERE vcpus>=? ORDER BY per_vcpu LIMIT ?", (a.min_vcpus, a.limit)):
            print("%-6s %-20s %-16s %4d vCPU %5d GB  $%.3f/hr  $%.4f/vCPU-hr" % (r[0], r[1], r[2], r[3], r[4] or 0, r[5], r[6]))
        return
    rows = build_rows(db, int(time.time()))
    out = []
    for r in rows:
        if a.gpu and not any(g.lower() in r["gpu"].lower() for g in a.gpu): continue
        if a.provider and r["provider"] not in a.provider: continue
        if not r["speed"] or (r["vram_gb"] or 0) < a.min_vram or (a.bf16 and not r["bf16"]): continue
        lam = r["int_per_hr"] if r["int_per_hr"] is not None else a.unknown_per_day / 24
        eff = r["price"] * max(1, r["gpu_count"] / a.ngpu) / (1 - min(lam * a.lost, 0.9))
        out.append((a.job * eff / r["speed"], r, lam))
    out.sort(key=lambda x: x[0])
    seen = set()
    print("cost$  provider  gpu x n  region  $/gpu-hr  speed  MTBF_h  tier-ish  note")
    for cost, r, lam in out:
        k = (r["provider"], r["gpu"])
        if k in seen: continue
        seen.add(k)
        print("%6.0f  %-7s %-24s x%-2d %-14s %7.3f %5.2f %7s  %s" % (cost, r["provider"], r["gpu"], r["gpu_count"], r["region"], r["price"],
              r["speed"], "-" if r["int_per_hr"] is None else "%.0f" % (1 / lam), (r["note"] or "")[:50]))
        if len(seen) >= a.limit: break


if __name__ == "__main__":
    main()
