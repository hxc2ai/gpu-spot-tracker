"""Approximate GPU specs used to turn $/hr into $/unit-of-work.

tflops = dense tensor TFLOPS for bf16 (fp16 where bf16 is unsupported), fp32 accumulate. Approximate
vendor figures; only RTX PRO 6000 / H100 / H200 have throughput measured on the owner's real workload
(hybrid_reasoning 4B SFT, tokens/s). Everything else scales those by TFLOPS, which is an estimate.
"""
from __future__ import annotations
import re

H100_TOK_S = 7300.0  # measured: 4B full SFT, stage A, 1x H100 80GB

# (regex on normalised name, vram_gb, tflops, bf16_supported, measured_tok_s or None)
_SPECS: list[tuple[str, int, float | None, bool, float | None]] = [
    (r"b300", 288, 2250, True, None), (r"gb200", 192, 2500, True, None), (r"b200", 180, 2250, True, None),
    (r"h200", 141, 989, True, 7400), (r"h100", 80, 989, True, 7300),
    (r"mi300x", 192, 1307, True, None),
    (r"a10080", 80, 312, True, None), (r"a10040", 40, 312, True, None), (r"a100", 40, 312, True, None),
    (r"rtxpro6000", 96, 504, True, 4400),
    (r"l40s", 48, 362, True, None), (r"l40", 48, 181, True, None), (r"l4", 24, 121, True, None),
    (r"a10g", 24, 70, True, None), (r"a10", 24, 125, True, None), (r"a40", 48, 150, True, None),
    (r"rtxa6000", 48, 155, True, None), (r"rtxa5000", 24, 111, True, None), (r"rtxa4500", 20, 94, True, None),
    (r"rtxa4000", 16, 77, True, None),
    (r"rtx6000ada", 48, 182, True, None), (r"rtx5000ada", 32, 130, True, None),
    (r"rtx4500ada", 24, 100, True, None), (r"rtx4000ada", 20, 53, True, None),
    (r"rtx5090", 32, 210, True, None), (r"rtx5080", 16, 113, True, None), (r"rtx5070ti", 16, 88, True, None),
    (r"rtx5070", 12, 62, True, None), (r"rtx5060ti", 16, 47, True, None), (r"rtx5060", 8, 38, True, None),
    (r"rtx4090", 24, 165, True, None), (r"rtx4080s", 16, 104, True, None), (r"rtx4080", 16, 97, True, None),
    (r"rtx4070s?ti", 16, 88, True, None), (r"rtx4070s", 12, 71, True, None), (r"rtx4070", 12, 58, True, None),
    (r"rtx4060ti", 16, 44, True, None), (r"rtx4060", 8, 30, True, None),
    (r"rtx3090ti", 24, 80, True, None), (r"rtx3090", 24, 71, True, None), (r"rtx3080ti", 12, 68, True, None),
    (r"rtx3080", 10, 60, True, None), (r"rtx3070ti", 8, 43, True, None), (r"rtx3070", 8, 40, True, None),
    (r"rtx3060ti", 8, 32, True, None), (r"rtx3060", 12, 25, True, None), (r"rtx3050", 8, 18, True, None),
    # no native bf16 (Turing/Volta): fp16 tensor figure
    (r"v10032", 32, 125, False, None), (r"v100", 16, 125, False, None), (r"t4", 16, 65, False, None),
    (r"titanv", 12, 110, False, None), (r"titanrtx", 24, 65, False, None), (r"rtx2080ti", 11, 54, False, None),
]


def norm(name: str) -> str:
    n = re.sub(r"[^a-z0-9]", "", name.lower())
    n = re.sub(r"(?<=\d)gb", "", n)
    for w in ("blackwell", "serveredition", "workstationedition", "generation", "hbm3", "sxm6pc", "sxm6ac", "sxm"):
        n = n.replace(w, "")
    return n.replace("nvidia", "").replace("geforce", "")


def spec_for(name: str) -> dict | None:
    n = norm(name)
    if "t4g" in n:           # AWS Graviton T4g = ARM host with a T4
        n = n.replace("t4g", "t4")
    for pat, vram, tf, bf16, tok in _SPECS:
        if re.fullmatch(pat, n) or (pat in ("a100",) and n.startswith("a100")):
            tok_s = tok or H100_TOK_S * tf / 989
            return dict(vram_gb=vram, tflops=tf, bf16=bf16, tok_s=round(tok_s),
                        speed=round(tok_s / H100_TOK_S, 3), measured=tok is not None)
    return None
