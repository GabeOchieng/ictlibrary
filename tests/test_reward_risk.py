"""Tests for the reward:risk rework — SD projection targets + structural stops."""

import pytest

from ictlib.concepts.ote import sd_projections, SD_OTE
from ictlib.analysis import analyze
from ictlib.scanner import scan
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


def test_sd_projection_math():
    # bullish leg 1.0800 -> 1.0900 (size 100 pips); -1.0 SD extends to 1.1000
    proj = sd_projections(1.0800, 1.0900)
    assert proj["-1.0SD"] == pytest.approx(1.1000)
    assert proj["-2.0SD"] == pytest.approx(1.1100)
    assert proj["-0.5SD"] == pytest.approx(1.0950)


def test_sd_projection_short_leg():
    # bearish leg 1.0900 -> 1.0800; -1.0 SD extends down to 1.0700
    proj = sd_projections(1.0900, 1.0800)
    assert proj["-1.0SD"] == pytest.approx(1.0700)


def test_structural_stop_is_tighter_than_sweep():
    a = analyze(candles(LONG_SETUP))
    s_struct = scan(a, min_score=2, stop_mode="structure")[0]
    s_sweep = scan(a, min_score=2, stop_mode="sweep")[0]
    # structural stop sits at the PD-array edge, above the sweep extreme -> tighter
    assert s_struct.stop > s_sweep.stop
    assert s_struct.risk < s_sweep.risk


def test_sd_targets_extend_reward():
    a = analyze(candles(LONG_SETUP))
    with_sd = scan(a, min_score=2, use_sd_targets=True)[0]
    without = scan(a, min_score=2, use_sd_targets=False)[0]
    # SD projections push the furthest target higher -> bigger best-case R
    assert max(with_sd.targets) >= max(without.targets)


def test_structural_stop_keeps_long_valid():
    s = scan(analyze(candles(LONG_SETUP)), min_score=2, stop_mode="structure")[0]
    assert s.direction == "long"
    lo, hi = s.entry_zone
    assert s.stop < s.entry            # stop still below entry for a long
    assert s.rr is not None and s.rr > 0
