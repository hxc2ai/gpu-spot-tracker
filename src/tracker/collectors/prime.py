"""Prime Intellect spot prices from GET /api/v1/availability/gpu-summary (needs PRIME_API_KEY, read-only).
Shape: {gpuType: {gpuCount: {"cheapest"|region: {onDemand, communityPrice, spotPrice}}}}. The /availability/gpus
listing returned 0 items with this key, so the summary is used. Prices appear to be for the WHOLE config
(H100 x2 on-demand is $10.75), so they are divided by the GPU count; flagged in the note (unverified)."""
from __future__ import annotations
import os, re
from ..models import Offer

URL = "https://api.primeintellect.ai/api/v1/availability/gpu-summary"
_NAMES = {"RTX_PRO_6000B": "RTX PRO 6000", "RTX6000Ada": "RTX 6000 Ada"}


def gpu_name(t: str) -> str | None:
    m = re.match(r"(.+?)_(\d+)GB$", t)
    if not m:
        return None
    base, vram = m.group(1), m.group(2)
    if base in _NAMES:
        return _NAMES[base]
    return f"{base} {vram}GB" if base == "A100" else base.replace("_", " ")


def enabled() -> bool:
    return bool(os.environ.get("PRIME_API_KEY"))


def collect(client) -> list[Offer]:
    r = client.get(URL, headers={"Authorization": f"Bearer {os.environ['PRIME_API_KEY']}"}, timeout=30)
    r.raise_for_status()
    out: dict[str, Offer] = {}
    for gtype, by_count in r.json().items():
        gpu = gpu_name(gtype)
        if not gpu:
            continue
        for cnt, regions in by_count.items():
            for region, p in regions.items():
                spot = p.get("spotPrice")
                if region == "cheapest" or spot is None:
                    continue
                n = int(cnt)
                o = Offer("primeintellect", gpu, region, spot / n, n,
                          note="spot, may be interrupted with or without notice; price assumed per whole config")
                if o.key not in out or o.price < out[o.key].price:
                    out[o.key] = o
    return list(out.values())
