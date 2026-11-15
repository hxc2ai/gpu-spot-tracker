"""Vast.ai interruptible offers. Needs VAST_API_KEY (read-only) and ALLOW_VAST_STORE=1.
NOTE: Vast.ai's ToS restricts automated collection into a database without written
permission. Enabling this is the owner's decision; output is only published to the
access-gated /analytics section, never the public page."""
from __future__ import annotations
import os
from ..models import Offer, canon_gpu

URL = "https://console.vast.ai/api/v0/bundles/"
MIN_RELIABILITY = 0.95


def enabled() -> bool:
    return bool(os.environ.get("VAST_API_KEY")) and os.environ.get("ALLOW_VAST_STORE") == "1"


def collect(client) -> list[Offer]:
    body = {"type": "bid", "rentable": {"eq": True}, "verified": {"eq": True},
            "limit": 1000, "order": [["dph_total", "asc"]]}
    r = client.post(URL, json=body, timeout=60,
                    headers={"Authorization": f"Bearer {os.environ['VAST_API_KEY']}"})
    r.raise_for_status()
    out: dict[str, Offer] = {}
    for o in r.json().get("offers", []):
        gpu = canon_gpu(o.get("gpu_name", ""))
        n = o.get("num_gpus") or 1
        bid = o.get("min_bid")
        rel = o.get("reliability2", o.get("reliability"))
        if not gpu or not bid or (rel is not None and rel < MIN_RELIABILITY):
            continue
        # min_bid is the interruptible floor; hosts can be outbid at any time.
        region = (o.get("geolocation") or "?").split(",")[-1].strip() or "?"
        off = Offer("vast", gpu, region, bid / n, n, p_int=None,
                    reliability=rel, note="min_bid; interruptible")
        cur = out.get(off.key)
        if cur is None or off.price < cur.price:
            out[off.key] = off
    return list(out.values())
