# Spot GPU tracker

Collects spot/preemptible GPU prices (AWS/GCP/Azure via the SkyPilot catalog + AWS Spot Advisor, Lium, Vast.ai),
stores change-only history in SQLite (private B2 bucket), ranks by stability-adjusted price, and deploys a static
site to Cloudflare Pages. `/` is public; `/analytics/*` (history + Vast.ai) must be gated with Cloudflare Access.

    set -a; source ~/.env; set +a
    uv run python -m tracker.run --force          # local collect -> data/tracker.db
    uv run python -m tracker.build_site           # -> dist/
    python -m http.server -d dist                 # preview

## One-time setup
1. Public GitHub repo; add Actions secrets: B2_ENDPOINT, B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET (bucket must be PRIVATE),
   CLOUDFLARE_COMPUTE_TRACKER_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, and optionally VAST_API_KEY.
2. Run the workflow once (workflow_dispatch) to create the Pages project `gpu-spot-tracker`.
3. Cloudflare Zero Trust -> Access -> Applications: self-hosted app for `gpu-spot-tracker.pages.dev/analytics*`
   with an Allow policy for your email (one-time PIN login).
