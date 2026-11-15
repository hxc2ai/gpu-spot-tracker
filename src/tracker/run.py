"""Collect: python -m tracker.run [--db data/tracker.db] [--b2] [--force]"""
from __future__ import annotations
import argparse, os, time, traceback
import httpx
from . import db as dbm
from .collectors import REGISTRY


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/tracker.db")
    ap.add_argument("--b2", action="store_true", help="pull DB from B2 first, push after")
    ap.add_argument("--force", action="store_true", help="ignore per-provider cadence")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    if a.b2:
        from . import b2
        print("pulled existing DB" if b2.pull(a.db) else "no DB in B2 yet; starting fresh")
    db = dbm.connect(a.db)
    now = int(time.time())
    with httpx.Client(headers={"User-Agent": "gpu-spot-tracker/0.1"}, follow_redirects=True) as client:
        for name, (mod, every) in REGISTRY.items():
            if hasattr(mod, "enabled") and not mod.enabled():
                print(f"{name}: disabled (missing key/flag)"); continue
            if not a.force and not dbm.due(db, name, every, now):
                print(f"{name}: not due"); continue
            try:
                offers = mod.collect(client)
                dbm.record_success(db, name, offers, now)
                if getattr(mod, "LAST_CPU", None):
                    dbm.replace_cpu(db, mod.LAST_CPU, now)
                print(f"{name}: {len(offers)} offers")
            except Exception as e:  # keep old data; mark failure
                traceback.print_exc()
                dbm.record_failure(db, name, repr(e), now); db.commit()
    db.close()
    if a.b2:
        b2.push(a.db)


if __name__ == "__main__":
    main()
