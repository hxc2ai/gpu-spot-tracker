"""Nebius preemptible GPU spot prices: public REST endpoint, no auth (docs.nebius.com/signup-billing/spot-prices).
Prices are per GPU-hour per platform per region and re-set about every 15 minutes. Since 2026-11-02 they are
uncapped and can exceed on-demand."""
from __future__ import annotations
import re
from ..models import Offer, canon_gpu

URL = "https://api.nebius.cloud/billing/v1alpha1/spot-price"


def collect(client) -> list[Offer]:
    out, token = [], None
    for _ in range(20):
        r = client.get(URL, params={"pageSize": 100, **({"pageToken": token} if token else {})}, timeout=30)
        r.raise_for_status()
        d = r.json()
        for it in d.get("items", []):
            title = re.sub(r"^Preemptible\s+NVIDIA®?\s+|\s+NVLink$", "", it.get("productTitle", ""))
            gpu = canon_gpu(title)
            p = it.get("price", {})
            if not gpu or p.get("unitTitle") != "GPU hour":
                continue
            out.append(Offer("nebius", gpu, it["region"], float(p["value"]), 1,
                             note=f"spot, uncapped; since {it.get('effectiveTime', '?')}; VM shape size not verified"))
        token = d.get("nextPageToken")
        if not token:
            break
    return out
