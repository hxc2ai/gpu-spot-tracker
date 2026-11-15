"""GCP 30-day Spot preemption rates from the Compute Engine beta advice.capacityHistory API.
Auth: Application Default Credentials (in Actions via Workload Identity Federation; service account needs
compute.advice.capacityHistory, included in roles/compute.viewer). Not supported by Google for N1+attached GPUs
(T4/V100/P4...), custom machine types or TPUs, so only A2/A3/A4/G2/G4 shapes are queried.
preemptionRate = preempted Spot VMs / Spot VMs that stopped that day (0..1). It is NOT an hourly hazard rate, so it
is shown as a stability signal (reliability = 1 - mean rate) and in the offer note, not turned into interruptions/hour."""
from __future__ import annotations
import os, time
from statistics import mean

# (GPU name as stored, GPUs per VM) -> machine type
MACHINES = {
    ("H100", 8): "a3-highgpu-8g", ("H200", 8): "a3-ultragpu-8g", ("B200", 8): "a4-highgpu-8g",
    ("A100 40GB", 1): "a2-highgpu-1g", ("A100 40GB", 8): "a2-highgpu-8g", ("A100 80GB", 1): "a2-ultragpu-1g",
    ("A100 80GB", 8): "a2-ultragpu-8g", ("L4", 1): "g2-standard-4", ("RTX PRO 6000", 1): "g4-standard-48",
}
URL = "https://compute.googleapis.com/compute/beta/projects/{p}/regions/{r}/advice/capacityHistory"


def enabled() -> bool:
    return bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and os.environ.get("GCP_PROJECT_ID"))


def _secs(iv: dict) -> float:
    from datetime import datetime
    f = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))
    try:
        return max(1.0, (f(iv["endTime"]) - f(iv["startTime"])).total_seconds())
    except (KeyError, ValueError):
        return 86400.0


def parse(resp: dict) -> tuple[float, float] | None:
    """-> (rate averaged over the window, rate over the last 7 days), both weighted by interval length
    (intervals are 1 day up to over a week long). None if there is no data."""
    hist = [(h["preemptionRate"], _secs(h.get("interval", {}))) for h in resp.get("preemptionHistory", []) if "preemptionRate" in h]
    if not hist:
        return None
    def wavg(items):
        tot = sum(w for _, w in items)
        return sum(r * w for r, w in items) / tot
    recent, acc = [], 0.0
    for r, w in reversed(hist):
        if acc >= 7 * 86400:
            break
        recent.append((r, w)); acc += w
    return wavg(hist), wavg(recent)


def run(db, client, now: int) -> int:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    sess = AuthorizedSession(creds)
    project = os.environ["GCP_PROJECT_ID"]
    wanted = db.execute("SELECT DISTINCT gpu, gpu_count, region FROM offers WHERE provider='gcp'").fetchall()
    n, errors = 0, []
    for gpu, cnt, region in wanted:
        mt = MACHINES.get((gpu, int(cnt)))
        if not mt:
            continue
        body = {"instanceProperties": {"machineType": mt, "scheduling": {"provisioningModel": "SPOT"}},
                "types": ["PREEMPTION", "PRICE"]}
        r = sess.post(URL.format(p=project, r=region), json=body, timeout=30)
        if r.status_code != 200:
            errors.append(f"{mt}/{region}: {r.status_code} {r.text[:120]}")
            continue
        if n == 0 and not errors:
            j = r.json(); ph = j.get("priceHistory", []); print("gcp price sample:", mt, region, len(ph), "points;", str(ph[:2]).replace("\n", " "), "...", str(ph[-1:]))  # one-time schema check (public data)
        p = parse(r.json())
        if p:
            db.execute("INSERT OR REPLACE INTO gcp_preempt VALUES(?,?,?,?,?,?,?)", (gpu, int(cnt), region, mt, p[0], p[1], now))
            n += 1
        time.sleep(0.2)
    db.commit()
    if errors and not n:
        raise RuntimeError("; ".join(errors[:3]))
    if errors:
        print("gcp_preempt partial errors:", "; ".join(errors[:3]))
    return n
