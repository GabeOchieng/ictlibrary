"""Tests for the refinement tranche: fib body-anchoring, mitigation lifecycle,
stop-run classification, 90-minute cycle, reclaimed OBs."""

from datetime import datetime, timezone

import pytest

from ictlib.concepts.ote import measured_leg, sd_projections
from ictlib.concepts.mitigation import mitigation_state
from ictlib.concepts.quarterly import ninety_minute_cycle
from ictlib.analysis import analyze
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


# --------------------------------------------------------------------------- #
# fib body-anchoring
# --------------------------------------------------------------------------- #
def test_measured_leg_uses_bodies_not_wicks():
    # a bull leg: bodies span 1.00 (low) to 1.05 (high); wicks reach 0.98 / 1.07
    rows = [(1.00, 1.03, 0.98, 1.02), (1.02, 1.07, 1.01, 1.05)]
    cs = candles(rows)
    body_start, body_end = measured_leg(cs, 0, 1, "bull", "body")
    wick_start, wick_end = measured_leg(cs, 0, 1, "bull", "wick")
    assert body_start == pytest.approx(1.00) and body_end == pytest.approx(1.05)
    assert wick_start == pytest.approx(0.98) and wick_end == pytest.approx(1.07)
    # different anchors -> different projection levels
    assert sd_projections(*measured_leg(cs, 0, 1, "bull", "body")) != \
           sd_projections(*measured_leg(cs, 0, 1, "bull", "wick"))


# --------------------------------------------------------------------------- #
# mitigation lifecycle
# --------------------------------------------------------------------------- #
def test_mitigation_states():
    lo, hi = 1.0800, 1.0820          # zone, mid 1.0810; bullish support
    base = candles([(1.09, 1.091, 1.089, 1.0905)])  # index 0 = formation
    def state(reach_low):
        cs = base + candles([(1.088, 1.089, reach_low, 1.0885)])
        return mitigation_state(cs, 0, lo, hi, "bull")
    assert state(1.0830) == "fresh"        # never reached the zone
    assert state(1.0815) == "partial"      # into the zone but above mid
    assert state(1.0805) == "mitigated"    # past the midpoint
    assert state(1.0795) == "consumed"     # through the far edge


# --------------------------------------------------------------------------- #
# 90-minute cycle
# --------------------------------------------------------------------------- #
def test_ninety_minute_cycle():
    # 12:00 UTC = 08:00 NY (EDT). Session quarter starts 06:00 NY, so this is
    # 120 min in -> 2nd 90-min cycle, 30 min in -> 2nd mini-quarter (manipulation).
    ts = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    cycle, mini, phase = ninety_minute_cycle(ts)
    assert cycle == 2 and mini == "Q2" and phase == "manipulation"
    # start of a session quarter -> cycle 1, Q1 accumulation (06:00 NY = 10:00 UTC)
    c1 = ninety_minute_cycle(datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc))
    assert c1 == (1, "Q1", "accumulation")


# --------------------------------------------------------------------------- #
# stop-run classification + reclaimed OB via analyze
# --------------------------------------------------------------------------- #
def test_analyze_exposes_refinements():
    a = analyze(candles(LONG_SETUP))
    su = a.summary()
    for k in ("reclaimed_obs", "stop_runs"):
        assert k in su
    # the SSL sweep in the sample runs into a bullish PD array
    assert any(r["into"] in ("FVG", "OB", "breaker") for r in a.stop_runs)
