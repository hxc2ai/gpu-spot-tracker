"""AWS/GCP/Azure spot prices from the open SkyPilot catalog (Apache-2.0), plus
AWS Spot Advisor interruption bands (no key needed)."""
from __future__ import annotations
import csv, io, math, os
from ..models import Offer, canon_gpu

LAST_CPU: list[dict] = []   # CPU-only spot instances from the last collect(), read by run.py
BASE = "https://raw.githubusercontent.com/skypilot-org/skypilot-catalog/master/catalogs/v8/{c}/vms.csv"
ADVISOR = "https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json"
BAND_MID = [0.025, 0.075, 0.125, 0.175, 0.25]  # monthly interruption-frequency band midpoints


def per_hour(p_month: float) -> float:
    return -math.log(1 - p_month) / 720  # Poisson rate per hour


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
    LAST_CPU.clear()
    cpu_best: dict[tuple, dict] = {}
    live_aws = bool(os.environ.get("AWS_COMPUTE_TRACKER_ACCESS_KEY_ID"))   # aws_live collector replaces the catalog rows
    for cloud in ("aws", "gcp", "azure"):
        text = client.get(BASE.format(c=cloud), timeout=120).text
        for r in csv.DictReader(io.StringIO(text)):
            v, sp = _f(r.get("vCPUs")), _f(r.get("SpotPrice"))
            if not r.get("AcceleratorName") and r.get("InstanceType") and v and v >= 8 and sp \
                    and r.get("Arch", "x86_64") in ("x86_64", ""):
                k = (cloud, r["InstanceType"])
                if k not in cpu_best or sp < cpu_best[k]["price"]:
                    cpu_best[k] = dict(provider=cloud, instance=r["InstanceType"], region=r["Region"], vcpus=v,
                                       mem_gb=_f(r.get("MemoryGiB")), price=sp, per_vcpu=sp / v)
            if cloud == "aws" and live_aws:
                continue
            gpu = canon_gpu(r.get("AcceleratorName", ""))
            price, n = _f(r.get("SpotPrice")), _f(r.get("AcceleratorCount"))
            if not gpu or not price or not n or n < 1:
                continue
            o = Offer(cloud, gpu, r["Region"], price / n, int(n))
            if cloud == "gcp":
                o.note = "GCP GPU SKU price: for attachable GPUs this may exclude the host VM (vCPU/RAM)"
            if cloud == "aws":
                b = bands.get(r["Region"], {}).get(r["InstanceType"])
                if b is not None:
                    o.p_int = per_hour(BAND_MID[b["r"]])
                    o.note = f"AWS interruption band {labels[b['r']]}/month on {r['InstanceType']}"
            cur = out.get(o.key)
            if cur is None or o.price < cur.price:
                out[o.key] = o
    LAST_CPU.extend(sorted(cpu_best.values(), key=lambda x: x["per_vcpu"])[:400])
    return list(out.values())
