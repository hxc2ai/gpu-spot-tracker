from tracker.models import canon_gpu
from tracker.build_site import vol


def test_canon():
    assert canon_gpu("H100 80GB HBM3") == "H100"
    assert canon_gpu("RTXPRO6000") == "RTX PRO 6000"
    assert canon_gpu("Radeon MI25") is None
    assert canon_gpu("Virtex UltraScale+ (VU47P)") is None


def test_vol_needs_a_day():
    assert vol([(1000, 1.0)], 1000 + 3600) is None
    assert vol([(0, 1.0)], 3 * 86400) == 0.0


def test_gcp_parse():
    from tracker.collectors.gcp_preempt import parse
    day = lambda d: {"startTime": f"2026-10-{d:02d}T00:00:00Z", "endTime": f"2026-10-{d + 1:02d}T00:00:00Z"}
    r = {"preemptionHistory": [{"interval": {"startTime": "2026-10-01T00:00:00Z", "endTime": "2026-10-09T00:00:00Z"}, "preemptionRate": 0.0},
                               {"interval": day(9), "preemptionRate": 0.5}]}
    a, rc = parse(r)
    assert abs(a - 0.5 / 9) < 1e-9 and abs(rc - 0.5 / 9) < 1e-9   # 8-day zero interval dilutes the 1-day 0.5
    assert parse({}) is None
