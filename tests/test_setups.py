"""Tests for named models (Silver Bullet, Judas Swing, 2022 model, Unicorn)."""

from ictlib.setups import classify_models, find_unicorns
from ictlib.analysis import analyze
from ictlib.scanner import scan
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


# --------------------------------------------------------------------------- #
# classify_models (pure)
# --------------------------------------------------------------------------- #
def test_2022_model_requires_killzone_bias_fvg():
    m = classify_models(killzone="NY AM", sb_window=False,
                        sweep_killzone="London Open", bias_aligned=True, has_fvg=True)
    assert "ICT 2022 Model" in m


def test_silver_bullet_needs_sb_window():
    base = dict(killzone="NY AM", sweep_killzone=None, bias_aligned=True, has_fvg=True)
    assert "Silver Bullet" not in classify_models(sb_window=False, **base)
    assert "Silver Bullet" in classify_models(sb_window=True, **base)


def test_judas_swing_from_session_open_sweep():
    m = classify_models(killzone=None, sb_window=False,
                        sweep_killzone="London Open", bias_aligned=True, has_fvg=False)
    assert "Judas Swing" in m
    # NY PM open is not a Judas killzone
    m2 = classify_models(killzone=None, sb_window=False,
                         sweep_killzone="NY PM", bias_aligned=True, has_fvg=False)
    assert "Judas Swing" not in m2


def test_no_models_without_bias():
    assert classify_models(killzone="NY AM", sb_window=True,
                           sweep_killzone="NY AM", bias_aligned=False, has_fvg=True) == []


# --------------------------------------------------------------------------- #
# Signal carries model tags
# --------------------------------------------------------------------------- #
def test_signal_models_field_populated():
    a = analyze(candles(LONG_SETUP))
    s = scan(a)[0]
    assert isinstance(s.models, list)
    # the sample's MSS is in a killzone with bullish bias and an MSS FVG
    assert "ICT 2022 Model" in s.models


# --------------------------------------------------------------------------- #
# Unicorn
# --------------------------------------------------------------------------- #
def test_unicorn_requires_all_four(monkeypatch):
    from ictlib.models import Breaker, FVG, Sweep
    from datetime import datetime, timezone

    class FakeMTF:
        bias = "bullish"
        def aligned(self, d):
            return d == "long"

    class FakeAnalysis:
        bias = "bullish"
        mtf = None
        # a bullish breaker with a nested bullish FVG, and a prior sweep
        breakers = [Breaker(index=10, ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
                            direction="bull", low=1.0800, high=1.0820,
                            ob_index=8, break_index=10)]
        fvgs = [FVG(index=11, ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    direction="bull", low=1.0805, high=1.0815)]  # ce 1.0810 inside breaker
        sweeps = [Sweep(index=5, ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        kind="SSL", level=1.0790, extreme=1.0785, close=1.0795,
                        wick_pct=0.7, pool_index=3)]

    a = FakeAnalysis()
    uni = find_unicorns(a)
    assert len(uni) == 1 and uni[0].direction == "bull"

    # remove the prior sweep -> no Unicorn
    a.sweeps = []
    assert find_unicorns(a) == []
