from __future__ import annotations
from dataclasses import dataclass
import re

# Non-GPU accelerators we ignore.
_SKIP = re.compile(r"virtex|inferentia|trainium|gaudi|xilinx|radeon pro v|vu\d|habana|tpu", re.I)
_ALIASES = {
    "A100-80GB": "A100 80GB", "A100-40GB": "A100 40GB", "A100": "A100 40GB",
    "H100-MEGA": "H100", "H100-80GB": "H100",
}


def canon_gpu(name: str) -> str | None:
    n = (name or "").strip()
    if not n or _SKIP.search(n):
        return None
    n = re.sub(r"^(nvidia|geforce|tesla|amd instinct)\s+", "", n, flags=re.I)
    n = _ALIASES.get(n, n)
    n = re.sub(r"\s+", " ", n).replace("RTX-", "RTX ")
    n = re.sub(r"^RTX ?PRO ?(\d+)", r"RTX PRO \1", n)
    n = re.sub(r"^(H100|H200)\b.*", r"\1", n)          # "H100 80GB HBM3" -> "H100"
    n = re.sub(r"^RTX 6000 Ada.*", "RTX 6000 Ada", n)
    if re.match(r"(Radeon MI25|M60|M10)", n):          # vGPU slices, not whole GPUs
        return None
    return n


@dataclass
class Offer:
    provider: str
    gpu: str
    region: str
    price: float                 # USD per GPU-hour, spot/interruptible
    gpu_count: int = 1
    p_int: float | None = None   # estimated hourly interruption probability
    reliability: float | None = None  # 0-1 host reliability if the source gives one
    note: str = ""               # e.g. "AWS band 5-10%"

    @property
    def key(self) -> str:
        return f"{self.provider}|{self.gpu}|{self.region}"
