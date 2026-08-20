"""Unit tests for the individual ICT concept detectors."""

from datetime import datetime, timezone

import pytest

from ictlib.models import Candle
from ictlib.concepts.displacement import displacement_direction, avg_body
from ictlib.concepts.fvg import find_fvgs
from ictlib.concepts.structure import find_swings, find_structure_events, current_bias
from ictlib.concepts.order_blocks import find_order_blocks
from ictlib.concepts.liquidity import find_pools, find_sweeps, infer_pip_size
from ictlib.concepts.killzones import active_killzone, in_silver_bullet, ny_minutes
from ictlib.concepts.ote import ote_from_leg

from _helpers import candles


# --------------------------------------------------------------------------- #
# Candle geometry
# --------------------------------------------------------------------------- #
def test_candle_geometry():
    c = Candle(datetime(2026, 1, 1, tzinfo=timezone.utc), 10, 14, 9, 13)
    assert c.range == 5
    assert c.body == 3
    assert c.body_high == 13 and c.body_low == 10
    assert c.upper_wick == 1 and c.lower_wick == 1
    assert c.is_bull and not c.is_bear


def test_candle_requires_tz():
    with pytest.raises(ValueError):
        Candle(datetime(2026, 1, 1), 1, 2, 0.5, 1.5)


# --------------------------------------------------------------------------- #
# Displacement
# --------------------------------------------------------------------------- #
def test_displacement_bull():
    # 10 small candles then one wide-body bullish displacement
    rows = [(1.0, 1.02, 0.99, 1.01)] * 10
    rows.append((1.01, 1.20, 1.008, 1.19))  # big body, tiny wicks, close near high
    cs = candles(rows)
    assert displacement_direction(cs, 10) == "bull"


def test_not_displacement_small_body():
    rows = [(1.0, 1.02, 0.99, 1.01)] * 10 + [(1.01, 1.05, 0.97, 1.015)]
    cs = candles(rows)
    assert displacement_direction(cs, 10) is None


def test_avg_body():
    cs = candles([(1, 2, 0, 1.5)] * 5)  # body 0.5 each
    assert avg_body(cs, 5, lookback=5) == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# FVG
# --------------------------------------------------------------------------- #
def test_bullish_fvg():
    # n-1 high=1.010, n huge bull, n+1 low=1.05 -> gap [1.010, 1.05]
    rows = [(1.0, 1.02, 0.99, 1.01)] * 10
    rows += [(1.00, 1.010, 0.999, 1.005),   # n-1
             (1.01, 1.20, 1.008, 1.19),     # n displacement
             (1.15, 1.22, 1.05, 1.20)]      # n+1 (low 1.05 > n-1 high 1.010)
    cs = candles(rows)
    fvgs = find_fvgs(cs)
    bull = [f for f in fvgs if f.direction == "bull" and f.index == 11]
    assert bull, "expected a bullish FVG at the displacement candle"
    f = bull[0]
    assert f.low == pytest.approx(1.010) and f.high == pytest.approx(1.05)
    assert f.ce == pytest.approx((1.010 + 1.05) / 2)


def test_no_fvg_when_wicks_overlap():
    rows = [(1.0, 1.02, 0.99, 1.01)] * 10
    rows += [(1.00, 1.05, 0.999, 1.01), (1.01, 1.20, 1.008, 1.19),
             (1.10, 1.22, 1.00, 1.20)]  # n+1 low 1.00 < n-1 high 1.05 -> overlap
    cs = candles(rows)
    assert not [f for f in find_fvgs(cs) if f.index == 11]


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def test_swings():
    # clear peak at idx2, trough at idx5
    rows = [(1, 1.1, 0.9, 1.0), (1, 1.2, 0.9, 1.1), (1, 1.5, 0.9, 1.4),
            (1, 1.2, 0.9, 1.0), (1, 1.1, 0.5, 0.6), (1, 1.0, 0.3, 0.4),
            (1, 1.1, 0.6, 1.0), (1, 1.2, 0.7, 1.1)]
    cs = candles(rows)
    sw = find_swings(cs, width=2)
    highs = [s.index for s in sw if s.kind == "high"]
    lows = [s.index for s in sw if s.kind == "low"]
    assert 2 in highs
    assert 5 in lows


def test_choch_then_bos_and_bias():
    from ictlib.analysis import analyze
    from ictlib.sample_setups import LONG_SETUP
    a = analyze(candles(LONG_SETUP))
    kinds = [(e.kind, e.direction) for e in a.events]
    assert ("MSS", "bull") in kinds
    assert current_bias(a.events) == "bullish"


# --------------------------------------------------------------------------- #
# Order blocks
# --------------------------------------------------------------------------- #
def test_order_block_bull():
    from ictlib.sample_setups import LONG_SETUP
    cs = candles(LONG_SETUP)
    sw = find_swings(cs)
    ev = find_structure_events(cs, sw)
    obs = find_order_blocks(cs, ev)
    assert any(o.direction == "bull" for o in obs)


# --------------------------------------------------------------------------- #
# Liquidity
# --------------------------------------------------------------------------- #
def test_ssl_sweep():
    # a swing low then a candle that wicks below and closes back above
    rows = [(1.10, 1.11, 1.09, 1.10), (1.10, 1.11, 1.08, 1.09),
            (1.09, 1.10, 1.06, 1.085),   # idx2 swing low 1.06
            (1.085, 1.10, 1.083, 1.095), (1.095, 1.11, 1.09, 1.10),
            (1.10, 1.105, 1.04, 1.098)]  # idx5 sweeps 1.06: low 1.04, close 1.098
    cs = candles(rows)
    sw = find_swings(cs)
    pools = find_pools(sw, pip=0.0001)
    sweeps = find_sweeps(cs, pools)
    assert any(s.kind == "SSL" for s in sweeps)


def test_equal_lows_pool():
    # two confirmed (width-2) swing lows at 1.0800 and 1.0802 -> EQL within 5 pips
    rows = [
        (1.095, 1.100, 1.090, 1.096),   # 0
        (1.094, 1.098, 1.088, 1.092),   # 1
        (1.090, 1.095, 1.0800, 1.091),  # 2  swing low 1.0800
        (1.091, 1.096, 1.086, 1.093),   # 3
        (1.093, 1.097, 1.087, 1.094),   # 4
        (1.092, 1.096, 1.0802, 1.093),  # 5  swing low 1.0802
        (1.093, 1.098, 1.088, 1.095),   # 6
        (1.095, 1.101, 1.090, 1.099),   # 7
    ]
    cs = candles(rows)
    sw = find_swings(cs)
    pools = find_pools(sw, pip=0.0001, eq_tolerance_pips=5)
    assert any(p.label == "EQL" for p in pools)


def test_infer_pip():
    jpy = candles([(150.0, 150.2, 149.8, 150.1)])
    eur = candles([(1.08, 1.082, 1.078, 1.081)])
    assert infer_pip_size(jpy) == 0.01
    assert infer_pip_size(eur) == 0.0001


# --------------------------------------------------------------------------- #
# Killzones (DST-aware)
# --------------------------------------------------------------------------- #
def test_killzone_ny_am_edt():
    # Aug -> EDT (UTC-4); 13:00 UTC = 09:00 NY -> NY AM
    ts = datetime(2026, 8, 20, 13, 0, tzinfo=timezone.utc)
    assert active_killzone(ts) == "NY AM"


def test_killzone_ny_am_est():
    # Jan -> EST (UTC-5); 14:00 UTC = 09:00 NY -> NY AM
    ts = datetime(2026, 1, 20, 14, 0, tzinfo=timezone.utc)
    assert active_killzone(ts) == "NY AM"


def test_killzone_asia_wrap():
    # Aug EDT; 01:00 UTC = 21:00 NY -> Asia (wraps midnight)
    ts = datetime(2026, 8, 20, 1, 0, tzinfo=timezone.utc)
    assert active_killzone(ts) == "Asia"


def test_silver_bullet():
    # 14:30 UTC Aug = 10:30 NY -> SB NY AM
    ts = datetime(2026, 8, 20, 14, 30, tzinfo=timezone.utc)
    assert in_silver_bullet(ts)


# --------------------------------------------------------------------------- #
# OTE
# --------------------------------------------------------------------------- #
def test_ote_bull_zone():
    ote = ote_from_leg(1.0800, 1.0900, "bull")  # 100-pip leg
    assert ote.entry_705 == pytest.approx(1.0900 - 0.705 * 0.01)
    lo, hi = ote.zone
    assert lo < ote.entry_705 < hi
    assert ote.contains(ote.entry_705)
    assert not ote.contains(1.0895)  # shallow retrace, outside zone
