"""Live AWS spot prices via EC2 DescribeSpotPriceHistory (needs AWS_ACCESS_KEY_ID/SECRET with only
ec2:DescribeSpotPriceHistory). When enabled it replaces the daily SkyPilot AWS rows (see skypilot.py).
UNTESTED: no AWS credentials were available when this was written."""
from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor
from ..models import Offer
from .skypilot import ADVISOR, BAND_MID, per_hour

SHAPES = {  # instance type -> (GPU, GPU count)
    "p6-b200.48xlarge": ("B200", 8), "p5en.48xlarge": ("H200", 8), "p5e.48xlarge": ("H200", 8),
    "p5.48xlarge": ("H100", 8), "p4de.24xlarge": ("A100 80GB", 8), "p4d.24xlarge": ("A100 40GB", 8),
    "g6e.xlarge": ("L40S", 1), "g6e.12xlarge": ("L40S", 4), "g6e.48xlarge": ("L40S", 8),
    "g6.xlarge": ("L4", 1), "g5.xlarge": ("A10G", 1), "g4dn.xlarge": ("T4", 1), "p3.2xlarge": ("V100", 1),
}
REGIONS = ["us-east-1", "us-east-2", "us-west-2", "eu-west-1", "eu-north-1", "eu-central-1", "ap-northeast-1", "ap-south-1"]


def enabled() -> bool:
    return bool(os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))


def _region(region: str):
    import boto3
    ec2 = boto3.client("ec2", region_name=region)
    resp = ec2.describe_spot_price_history(InstanceTypes=list(SHAPES), ProductDescriptions=["Linux/UNIX"], MaxResults=1000)
    return region, resp.get("SpotPriceHistory", [])


def collect(client) -> list[Offer]:
    adv = client.get(ADVISOR, timeout=60).json()
    bands = {rg: v.get("Linux", {}) for rg, v in adv["spot_advisor"].items()}
    labels = [r["label"] for r in adv["ranges"]]
    best: dict[str, Offer] = {}
    with ThreadPoolExecutor(4) as ex:
        for region, hist in ex.map(_region, REGIONS):
            seen = set()
            for h in hist:  # newest first; keep the latest price per (instance, AZ)
                k = (h["InstanceType"], h["AvailabilityZone"])
                if k in seen:
                    continue
                seen.add(k)
                gpu, n = SHAPES[h["InstanceType"]]
                o = Offer("aws", gpu, region, float(h["SpotPrice"]) / n, n)
                b = bands.get(region, {}).get(h["InstanceType"])
                if b is not None:
                    o.p_int = per_hour(BAND_MID[b["r"]])
                    o.note = f"AWS band {labels[b['r']]}/month, live price on {h['InstanceType']}"
                if o.key not in best or o.price < best[o.key].price:
                    best[o.key] = o
    return list(best.values())
