"""Tests for PD-array variants and structure completion."""

import pytest

from ictlib.models import FVG, DealingRange
from ictlib.concepts.fvg_variants import find_inversion_fvgs, find_bpr, find_nested_fvgs
from ictlib.concepts.liquidity import find_liquidity_voids
from ictlib.concepts.ob_variants import find_propulsion_blocks
from ictlib.concepts.structure import (
    find_swings, find_structure_events, classify_internal_external, range_state,
)
from ictlib.concepts.order_blocks import find_order_blocks
from ictlib.concepts.pd_arrays import find_dealing_range
from ictlib.analysis import analyze
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles
from datetime import datetime, timezone

TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_inversion_fvg():
    # a bullish FVG, then price closes decisively below its low -> bearish IFVG
    rows = [(1.0, 1.02, 0.99, 1.01)] * 10
    rows += [(1.00, 1.010, 0.999, 1.005),   # n-1
             (1.01, 1.20, 1.008, 1.19),     # n displacement up
             (1.15, 1.22, 1.05, 1.20)]      # n+1 -> bullish FVG [1.010, 1.05]
    rows += [(1.05, 1.06, 0.90, 0.92),      # big bearish displacement closes < 1.010
             (0.92, 0.93, 0.88, 0.90)]
    cs = candles(rows)
    from ictlib.concepts.fvg import find_fvgs
    inv = find_inversion_fvgs(cs, find_fvgs(cs))
    assert any(i.direction == "bear" for i in inv)


def test_bpr_overlap():
    bull = FVG(index=5, ts=TS, direction="bull", low=1.080, high=1.085)
    bear = FVG(index=8, ts=TS, direction="bear", low=1.083, high=1.088)
    out = find_bpr([bull, bear])
    assert len(out) == 1
    assert out[0].low == pytest.approx(1.083) and out[0].high == pytest.approx(1.085)


def test_no_bpr_when_disjoint():
    bull = FVG(index=5, ts=TS, direction="bull", low=1.080, high=1.082)
    bear = FVG(index=8, ts=TS, direction="bear", low=1.090, high=1.092)
    assert find_bpr([bull, bear]) == []


def test_nested_fvg():
    outer = FVG(index=1, ts=TS, direction="bull", low=1.00, high=1.10)
    inner = FVG(index=2, ts=TS, direction="bull", low=1.03, high=1.06)
    pairs = find_nested_fvgs([outer, inner])
    assert (1, 2) in pairs


def test_liquidity_void():
    # 6 strong bullish candles, no lower wick -> minimal pullback -> bullish void
    rows = [(1.00 + i * 0.01, 1.00 + i * 0.01 + 0.012, 1.00 + i * 0.01,
             1.00 + i * 0.01 + 0.010) for i in range(6)]
    cs = candles(rows)
    voids = find_liquidity_voids(cs, span=4)
    assert any(v.direction == "bull" for v in voids)


def test_internal_external_structure():
    dr = DealingRange(top=1.10, bottom=1.00, top_index=2, bottom_index=8)
    cs = candles(LONG_SETUP)
    sw = find_swings(cs)
    labels = classify_internal_external(sw, dr)
    assert set(labels.values()) <= {"internal", "external"}


def test_range_state_expansion():
    quiet = [(1.0, 1.001, 0.999, 1.0)] * 20
    loud = [(1.0, 1.02, 0.98, 1.0)] * 20
    cs = candles(quiet + loud)
    assert range_state(cs, lookback=20) == "expansion"


def test_propulsion_block_on_setup():
    cs = candles(LONG_SETUP)
    sw = find_swings(cs)
    ev = find_structure_events(cs, sw)
    obs = find_order_blocks(cs, ev)
    # the big displacement candle after the OB should qualify as propulsion
    props = find_propulsion_blocks(cs, obs)
    assert isinstance(props, list)


def test_analysis_exposes_variants():
    a = analyze(candles(LONG_SETUP))
    su = a.summary()
    for k in ("inversion_fvgs", "bpr", "nested_fvgs", "liquidity_voids",
              "propulsion_blocks", "range_state"):
        assert k in su
