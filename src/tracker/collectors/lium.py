from __future__ import annotations
from ..models import Offer, canon_gpu

URL = "https://lium.io/api/public/v1/nodes"


def collect(client) -> list[Offer]:
    out: dict[str, Offer] = {}
    for n in client.get(URL, timeout=60).json()["nodes"]:
        if n.get("tier") != "spot" or not n.get("available_gpu_count"):
            continue
        gpu = canon_gpu(n.get("gpu_model", ""))
        price = n.get("price_per_gpu_hour")
        if not gpu or not price:
            continue
        up = n.get("provider_spot_avg_uptime_hours")
        o = Offer("lium", gpu, n.get("country_code") or "?", float(price), int(n["gpu_count"]),
                  p_int=min(1.0, 1.0 / up) if up else None,
                  reliability=n.get("reliability_score"),
                  note=f"avg spot uptime {up}h" if up else "")
        cur = out.get(o.key)
        if cur is None or o.price < cur.price:
            out[o.key] = o
    return list(out.values())
