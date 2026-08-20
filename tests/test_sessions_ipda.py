"""Tests for sessions, Asian range, and IPDA lookback levels."""

from datetime import datetime, timedelta, timezone

import pytest

from ictlib.models import Candle
from ictlib.concepts.sessions import session_of, session_range, all_session_ranges
from ictlib.concepts.asian_range import asian_range
from ictlib.concepts.ipda import ipda_levels
from ictlib.analysis import analyze

from _helpers import candles


def _at(hour_utc, minute=0, day=20):
    """A single candle at a given UTC hour on 2026-08-{day} (EDT: NY = UTC-4)."""
    return Candle(datetime(2026, 8, day, hour_utc, minute, tzinfo=timezone.utc),
                  1.08, 1.081, 1.079, 1.0805)


# --------------------------------------------------------------------------- #
# session_of  (Aug -> EDT, NY = UTC-4)
# --------------------------------------------------------------------------- #
def test_session_of_ny_am():
    # 13:00 UTC = 09:00 NY -> NY AM
    assert session_of(datetime(2026, 8, 20, 13, tzinfo=timezone.utc)) == "NY AM"


def test_session_of_asia_wraps_midnight():
    # 23:00 UTC = 19:00 NY -> Asia; and 05:00 UTC = 01:00 NY -> Asia
    assert session_of(datetime(2026, 8, 20, 23, tzinfo=timezone.utc)) == "Asia"
    assert session_of(datetime(2026, 8, 21, 5, tzinfo=timezone.utc)) == "Asia"


def test_session_of_outside():
    # 21:00 UTC = 17:00 NY -> between NY PM close (16:00) and Asia (18:00)
    assert session_of(datetime(2026, 8, 20, 21, tzinfo=timezone.utc)) is None


# --------------------------------------------------------------------------- #
# session_range
# --------------------------------------------------------------------------- #
def test_ny_am_session_range():
    # NY AM 08:00-12:00 NY = 12:00-16:00 UTC. Put a high spike and low spike inside.
    base = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)  # 08:00 NY
    cs = [
        Candle(base, 1.0800, 1.0820, 1.0795, 1.0810),
        Candle(base + timedelta(hours=1), 1.0810, 1.0860, 1.0805, 1.0850),  # high 1.0860
        Candle(base + timedelta(hours=2), 1.0850, 1.0855, 1.0780, 1.0790),  # low 1.0780
        Candle(base + timedelta(hours=3), 1.0790, 1.0800, 1.0785, 1.0795),
    ]
    sr = session_range(cs, "NY AM")
    assert sr is not None
    assert sr.high == pytest.approx(1.0860)
    assert sr.low == pytest.approx(1.0780)
    assert sr.eq == pytest.approx((1.0860 + 1.0780) / 2)


# --------------------------------------------------------------------------- #
# Asian range (KZ-anchored 20:00-00:00 NY = 00:00-04:00 UTC next day EDT)
# --------------------------------------------------------------------------- #
def test_asian_range_and_judas_sweep():
    # 20:00 NY 2026-08-20 = 00:00 UTC 2026-08-21 (EDT). Build 4 hourly bars,
    # then a bar that sweeps the low.
    base = datetime(2026, 8, 21, 0, tzinfo=timezone.utc)  # 20:00 NY prev day
    cs = [
        Candle(base, 1.0800, 1.0830, 1.0790, 1.0820),                    # high 1.0830
        Candle(base + timedelta(hours=1), 1.0820, 1.0825, 1.0770, 1.0780),  # low 1.0770
        Candle(base + timedelta(hours=2), 1.0780, 1.0810, 1.0775, 1.0800),
        Candle(base + timedelta(hours=3), 1.0800, 1.0815, 1.0795, 1.0805),
        # 04:00 UTC = 00:00 NY -> outside KZ window; sweeps the low
        Candle(base + timedelta(hours=4), 1.0805, 1.0808, 1.0750, 1.0800),
    ]
    ar = asian_range(cs, anchor="kz")
    assert ar is not None
    assert ar.high == pytest.approx(1.0830)
    assert ar.low == pytest.approx(1.0770)
    assert ar.swept_side == "low"
    proj = ar.projections()
    assert proj["up_1.0x"] == pytest.approx(1.0830 + (1.0830 - 1.0770))


# --------------------------------------------------------------------------- #
# IPDA lookback
# --------------------------------------------------------------------------- #
def test_ipda_lookback_levels():
    # 5 daily candles; 20/40/60-day levels collapse to the extremes of all 5.
    day0 = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    highs = [1.05, 1.09, 1.07, 1.12, 1.06]
    lows = [1.00, 1.02, 0.98, 1.04, 1.01]
    cs = [Candle(day0 + timedelta(days=i), 1.03, highs[i], lows[i], 1.04)
          for i in range(5)]
    ip = ipda_levels(cs)
    assert ip.days_used == 5
    assert ip.levels["20_high"] == pytest.approx(1.12)
    assert ip.levels["20_low"] == pytest.approx(0.98)
    # fewer than 60 days -> 60-day level uses all available, same extremes
    assert ip.levels["60_high"] == pytest.approx(1.12)


def test_ipda_lookback_respects_window():
    # 25 daily candles; the highest is on day 0, outside the last 20 days.
    day0 = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)
    cs = []
    for i in range(25):
        hi = 2.00 if i == 0 else 1.10 + i * 0.001
        cs.append(Candle(day0 + timedelta(days=i), 1.05, hi, 1.00, 1.06))
    ip = ipda_levels(cs)
    # 20-day window excludes the day-0 spike; 40-day includes it
    assert ip.levels["20_high"] < 2.00
    assert ip.levels["40_high"] == pytest.approx(2.00)


# --------------------------------------------------------------------------- #
# analysis integration + draw-on-liquidity
# --------------------------------------------------------------------------- #
def test_analysis_exposes_sessions_and_dol():
    from ictlib.sample_setups import LONG_SETUP
    a = analyze(candles(LONG_SETUP))
    su = a.summary()
    assert "session_ranges" in su and "ipda_days" in su
    # draw-on-liquidity returns sorted levels above the entry region
    up = a.draw_on_liquidity("up")
    down = a.draw_on_liquidity("down")
    assert up == sorted(up)
    assert down == sorted(down, reverse=True)
