# Project: cloud_compute_price_tracker

Spot/preemptible GPU price + stability tracker. Collectors -> SQLite (private B2) -> static site on Cloudflare Pages
(`gpu-spot-tracker.pages.dev`, owner-only via Cloudflare Access). GitHub Actions cron (every 15 min) runs `tracker.run`,
hourly `tracker.build_site` + `wrangler pages deploy`. Repo: github.com/hxc2ai/gpu-spot-tracker (public: code only, NO data).

## Reading the data (Claude Code can)
- The site is behind Access; Claude cannot read it. Use the DB instead: `set -a; source ~/.env; set +a;
  uv run python -m tracker.query --pull --gpu H100 --min-vram 80 --job 40` (pulls `price-tracker/tracker.db` from the private B2 bucket).
  `--cpu --min-vcpus 32` lists CPU-only spot boxes. Or open `data/tracker.db` with sqlite3: tables `offers`, `history`, `cpu_offers`, `provider_state`.
- Never print credentials. Never commit `data/` or `dist/`. The B2 bucket must stay private.

## Layout
- `src/tracker/collectors/*`: one module per source (`collect(client) -> list[Offer]`, optional `enabled()`); registered with a poll cadence in `collectors/__init__.py`.
- `src/tracker/gpu_specs.py`: VRAM / TFLOPS / bf16 / tok/s per GPU. Only H100, H200, RTX PRO 6000 throughput is measured (hybrid_reasoning 4B SFT); the rest is scaled by TFLOPS.
- `site/` (index.html, app.js, style.css): all ranking/recommendation logic runs in the browser from `data.json`.
- `.github/workflows/collect.yml`: secrets B2_*, CLOUDFLARE_COMPUTE_TRACKER_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, VAST_API_KEY (+ AWS_* when added).

## Gotchas
- `p_int` / `int_per_hr` = interruptions per HOUR (AWS monthly band -> Poisson rate; Lium = 1/avg spot uptime; Vast/GCP/Azure/Nebius unknown -> None).
- Offer key = provider|gpu|region|xN (N GPUs per rental). Price is per GPU; a shape bigger than the GPUs you use is billed in full.
- GCP catalog GPU rows may exclude the host VM cost. `aws_live` is UNTESTED (needs AWS creds); when AWS_ACCESS_KEY_ID is set it replaces the SkyPilot AWS rows.
- Vast.ai ToS forbids storing its data without written permission; owner chose to store it (`ALLOW_VAST_STORE=1`).
- Not done: GCP preemptionHistory (needs Compute API auth), Prime Intellect (needs key + real response to write the parser), Shadeform, TensorDock, CoreWeave/Hyperstack/Crusoe scrapers.
- Tests: `uv run pytest -q`. No `rm`/`pkill -f` in shell commands (owner preference); use Python/Edit instead.
