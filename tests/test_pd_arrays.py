"""Tests for PD arrays: dealing range, equilibrium, premium/discount."""

import pytest

from ictlib.models import DealingRange
from ictlib.analysis import analyze
from ictlib.concepts.structure import find_swings
from ictlib.concepts.pd_arrays import find_dealing_range, swing_degrees
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


# --------------------------------------------------------------------------- #
# DealingRange math (pure)
# --------------------------------------------------------------------------- #
def test_dealing_range_classify_and_depth():
    dr = DealingRange(top=1.1000, bottom=1.0000, top_index=10, bottom_index=0)
    assert dr.eq == pytest.approx(1.0500)
    assert dr.size == pytest.approx(0.1000)
    assert dr.classify(1.0800) == "premium"
    assert dr.classify(1.0200) == "discount"
    assert dr.classify(1.0500) == "equilibrium"
    # depth: +1 at top, -1 at bottom, 0 at EQ
    assert dr.depth(1.1000) == pytest.approx(1.0)
    assert dr.depth(1.0000) == pytest.approx(-1.0)
    assert dr.depth(1.0500) == pytest.approx(0.0)
    # the OTE 0.79 premium level sits at depth +0.79
    assert dr.depth(1.0500 + 0.79 * 0.05) == pytest.approx(0.79)


def test_contains():
    dr = DealingRange(1.10, 1.00, 5, 0)
    assert dr.contains(1.05) and not dr.contains(1.20)


# --------------------------------------------------------------------------- #
# Swing degree hierarchy (STH -> ITH -> LTH)
# --------------------------------------------------------------------------- #
def test_swing_degree_promotion():
    # five swing highs where the middle one is the tallest -> should reach ITH
    rows = []
    heights = [1.05, 1.08, 1.12, 1.07, 1.04]  # peak in the middle
    lowbase = 0.99
    for h in heights:
        # build a 3-candle up-down that leaves a swing high at h, low at lowbase
        rows += [
            (lowbase, lowbase + 0.005, lowbase - 0.005, lowbase + 0.004),
            (lowbase, h, lowbase, h - 0.002),          # the peak candle
            (lowbase, lowbase + 0.005, lowbase - 0.005, lowbase + 0.004),
        ]
    cs = candles(rows)
    sw = find_swings(cs, width=1)
    pts, deg = swing_degrees(sw, "high")
    assert max(deg) >= 2, "the tallest central swing high should promote to ITH+"


# --------------------------------------------------------------------------- #
# Dealing range from the canonical setup
# --------------------------------------------------------------------------- #
def test_dealing_range_on_setup():
    cs = candles(LONG_SETUP)
    dr = find_dealing_range(cs, find_swings(cs))
    assert dr is not None
    assert dr.top > dr.bottom
    assert dr.bottom <= dr.eq <= dr.top


def test_analysis_tags_pd_side_and_price_state():
    a = analyze(candles(LONG_SETUP))
    assert a.dealing_range is not None
    assert a.price_state in ("premium", "discount", "equilibrium")
    # every FVG / OB is tagged with a side of equilibrium
    for f in a.fvgs:
        assert f.pd_side in ("premium", "discount", "equilibrium")
    for o in a.order_blocks:
        assert o.pd_side in ("premium", "discount", "equilibrium")
    # summary exposes equilibrium + price_state
    su = a.summary()
    assert su["equilibrium"] is not None
    assert "price_state" in su


def test_fallback_range_without_swings():
    # too few candles to form swings -> fallback to visible extremes
    cs = candles([(1.10, 1.11, 1.09, 1.105), (1.105, 1.12, 1.10, 1.115)])
    dr = find_dealing_range(cs, find_swings(cs))
    assert dr is not None
    assert dr.top_degree == "RANGE" and dr.bottom_degree == "RANGE"
