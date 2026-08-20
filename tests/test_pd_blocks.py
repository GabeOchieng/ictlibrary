"""Tests for breaker blocks, rejection blocks, and volume imbalance."""

import pytest

from ictlib.analysis import analyze
from ictlib.concepts.structure import find_swings, find_structure_events
from ictlib.concepts.order_blocks import find_order_blocks
from ictlib.concepts.breaker_blocks import find_breakers
from ictlib.concepts.rejection_blocks import find_rejection_blocks
from ictlib.concepts.imbalance import find_volume_imbalances
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


# --------------------------------------------------------------------------- #
# Volume imbalance
# --------------------------------------------------------------------------- #
def test_bullish_volume_imbalance():
    # candle 1 opens (1.015) strictly above candle 0 close (1.010) -> bullish VI
    rows = [(1.000, 1.012, 0.999, 1.010), (1.015, 1.030, 1.013, 1.028)]
    vis = find_volume_imbalances(candles(rows))
    assert vis and vis[0].direction == "bull"
    assert vis[0].low == pytest.approx(1.010) and vis[0].high == pytest.approx(1.015)


def test_bearish_volume_imbalance():
    rows = [(1.030, 1.032, 1.018, 1.020), (1.015, 1.017, 1.000, 1.005)]
    vis = find_volume_imbalances(candles(rows))
    assert vis and vis[0].direction == "bear"
    assert vis[0].low == pytest.approx(1.015) and vis[0].high == pytest.approx(1.020)


def test_no_vi_when_open_equals_prev_close():
    rows = [(1.00, 1.01, 0.99, 1.005), (1.005, 1.02, 1.00, 1.015)]
    assert find_volume_imbalances(candles(rows)) == []


# --------------------------------------------------------------------------- #
# Rejection blocks
# --------------------------------------------------------------------------- #
def test_bullish_rejection_block():
    # long lower wick, close near the top -> bullish RB
    rows = [(1.020, 1.025, 1.000, 1.023)]  # body 1.020-1.023, lower wick 20/25=0.8
    rbs = find_rejection_blocks(candles(rows))
    assert rbs and rbs[0].direction == "bull"
    assert rbs[0].tip == pytest.approx(1.000)


def test_bearish_rejection_block():
    rows = [(1.003, 1.030, 1.000, 1.005)]  # long upper wick, close near bottom
    rbs = find_rejection_blocks(candles(rows))
    assert rbs and rbs[0].direction == "bear"
    assert rbs[0].tip == pytest.approx(1.030)


def test_rejection_block_key_level_filter():
    rows = [(1.020, 1.025, 1.000, 1.023)]
    # wick tip is 1.000; a key level far away means no RB
    assert find_rejection_blocks(candles(rows), key_levels=[1.050], tol=0.0005) == []
    # a key level at the tip keeps it
    assert find_rejection_blocks(candles(rows), key_levels=[1.000], tol=0.0005)


# --------------------------------------------------------------------------- #
# Breaker blocks
# --------------------------------------------------------------------------- #
def test_bullish_breaker_from_failed_bearish_ob():
    # bearish OB (idx3), a bearish break below the swing low, then a bullish
    # displacement (idx8) closing above the OB body -> the failed bearish OB
    # flips into a bullish breaker.
    rows = [
        (1.0050, 1.0060, 1.0040, 1.0055),   # 0
        (1.0055, 1.0058, 1.0020, 1.0025),   # 1 swing low ~1.0020
        (1.0025, 1.0075, 1.0024, 1.0070),   # 2 up
        (1.0070, 1.0090, 1.0065, 1.0085),   # 3 bullish -> bearish OB body [1.0070, 1.0085]
        (1.0085, 1.0088, 1.0060, 1.0065),   # 4 down
        (1.0065, 1.0068, 1.0010, 1.0015),   # 5 bearish displacement, close < swing low -> break
        (1.0015, 1.0020, 1.0000, 1.0005),   # 6 swing low
        (1.0005, 1.0010, 0.9990, 0.9995),   # 7 down
        (0.9995, 1.0130, 0.9990, 1.0125),   # 8 bullish displacement closes ABOVE OB high 1.0085
        (1.0125, 1.0140, 1.0075, 1.0085),   # 9 retest down into the flipped zone
    ]
    cs = candles(rows)
    sw = find_swings(cs, width=1)
    obs = find_order_blocks(cs, find_structure_events(cs, sw, width=1))
    assert any(o.direction == "bear" for o in obs), "expected a bearish OB to form"
    breakers = find_breakers(cs, obs)
    assert any(b.direction == "bull" for b in breakers), \
        f"expected a bullish breaker, got {[b.direction for b in breakers]}"


# --------------------------------------------------------------------------- #
# Analysis integration
# --------------------------------------------------------------------------- #
def test_analysis_exposes_new_pd_arrays():
    a = analyze(candles(LONG_SETUP))
    su = a.summary()
    for k in ("breakers", "rejection_blocks", "volume_imbalances"):
        assert k in su
    # detected instances (if any) are tagged with a PD side
    for coll in (a.breakers, a.rejection_blocks, a.volume_imbalances):
        for item in coll:
            assert item.pd_side in ("premium", "discount", "equilibrium")
