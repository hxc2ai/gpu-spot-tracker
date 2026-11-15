"""AWS/GCP/Azure spot prices from the open SkyPilot catalog (Apache-2.0), plus
AWS Spot Advisor interruption bands (no key needed)."""
from __future__ import annotations
import csv, io
from ..models import Offer, canon_gpu

BASE = "https://raw.githubusercontent.com/skypilot-org/skypilot-catalog/master/catalogs/v8/{c}/vms.csv"
ADVISOR = "https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json"
BAND_MID = [0.025, 0.075, 0.125, 0.175, 0.25]  # per-month rate bands; used as a rough proxy


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def collect(client) -> list[Offer]:
    adv = client.get(ADVISOR, timeout=60).json()
    bands = {rg: v.get("Linux", {}) for rg, v in adv["spot_advisor"].items()}
    labels = [r["label"] for r in adv["ranges"]]
    out: dict[str, Offer] = {}
    for cloud in ("aws", "gcp", "azure"):
        text = client.get(BASE.format(c=cloud), timeout=120).text
        for r in csv.DictReader(io.StringIO(text)):
            gpu = canon_gpu(r.get("AcceleratorName", ""))
            price, n = _f(r.get("SpotPrice")), _f(r.get("AcceleratorCount"))
            if not gpu or not price or not n or n < 1:
                continue
            o = Offer(cloud, gpu, r["Region"], price / n, int(n))
            if cloud == "aws":
                b = bands.get(r["Region"], {}).get(r["InstanceType"])
                if b is not None:
                    o.p_int = BAND_MID[b["r"]]
                    o.note = f"AWS interruption band {labels[b['r']]}/month on {r['InstanceType']}"
            cur = out.get(o.key)
            if cur is None or o.price < cur.price:
                out[o.key] = o
    return list(out.values())
