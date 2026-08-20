"""Tests for risk management and the backtester."""

import pytest

from ictlib.risk import (
    RiskParams, position_size, r_multiple, price_at_r, pips, size_signal,
)
from ictlib.backtest import backtest, Trade, _process, _close
from ictlib.analysis import analyze
from ictlib.scanner import scan
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


# --------------------------------------------------------------------------- #
# Risk math
# --------------------------------------------------------------------------- #
def test_position_size_formula():
    # $10,000 @ 1% = $100 risk; SL 20 pips; $10/pip/lot -> 0.5 lots
    p = RiskParams(equity=10_000, risk_pct=0.01, pip_value=10.0)
    lots = position_size(entry=1.0850, stop=1.0830, pip=0.0001, params=p)
    assert lots == pytest.approx(0.5, rel=1e-3)


def test_r_multiple_long_and_short():
    # long: entry 1.0850, stop 1.0830 (risk 20), target 1.0910 -> +3R
    assert r_multiple(1.0850, 1.0830, 1.0910) == pytest.approx(3.0)
    # short: entry 1.0850, stop 1.0870 (risk 20), target 1.0790 -> +3R
    assert r_multiple(1.0850, 1.0870, 1.0790) == pytest.approx(3.0)
    # a stop-out is -1R either way
    assert r_multiple(1.0850, 1.0830, 1.0830) == pytest.approx(-1.0)


def test_price_at_r_roundtrip():
    entry, stop = 1.0850, 1.0830
    px = price_at_r(entry, stop, 2.0)
    assert r_multiple(entry, stop, px) == pytest.approx(2.0)


def test_pips():
    assert pips(0.0020, 0.0001) == pytest.approx(20)


def test_size_signal():
    a = analyze(candles(LONG_SETUP))
    s = scan(a)[0]
    ss = size_signal(s, pip=a.pip, params=RiskParams(equity=10_000, risk_pct=0.01))
    assert ss.lots > 0
    assert ss.risk_dollars == pytest.approx(100.0)
    assert len(ss.target_rs) == len(s.targets)


# --------------------------------------------------------------------------- #
# Trade simulation mechanics (deterministic, no scanner)
# --------------------------------------------------------------------------- #
def _t(direction="long", entry=1.0850, stop=1.0830, target=1.0910):
    return Trade(direction=direction, signal_index=0, detected_index=0,
                 entry=entry, stop=stop, target=target, lots=1.0, score=3)


def test_long_fills_then_targets():
    cs = candles([
        (1.0860, 1.0865, 1.0855, 1.0862),   # 0 (detection bar, ignored)
        (1.0855, 1.0858, 1.0848, 1.0852),   # 1 touches entry 1.0850 -> fill
        (1.0860, 1.0912, 1.0858, 1.0908),   # 2 hits target 1.0910
    ])
    t = _t()
    _process(t, cs, 1, 8)
    assert t.status == "open" and t.entry_index == 1
    _process(t, cs, 2, 8)
    assert t.status == "closed" and t.exit_reason == "target"
    assert t.realized_r == pytest.approx(3.0)


def test_long_stops_out():
    cs = candles([
        (1.0860, 1.0865, 1.0855, 1.0862),
        (1.0855, 1.0858, 1.0848, 1.0852),   # fill at 1.0850
        (1.0850, 1.0852, 1.0825, 1.0828),   # hits stop 1.0830
    ])
    t = _t()
    _process(t, cs, 1, 8)
    _process(t, cs, 2, 8)
    assert t.status == "closed" and t.exit_reason == "stop"
    assert t.realized_r == pytest.approx(-1.0)


def test_pending_expires():
    cs = candles([(1.0900, 1.0905, 1.0895, 1.0902)] * 12)  # never touches 1.0850
    t = _t()
    for i in range(1, 11):
        _process(t, cs, i, entry_expiry=8)
    assert t.status == "cancelled"


def test_short_targets():
    t = _t(direction="short", entry=1.0850, stop=1.0870, target=1.0790)
    cs = candles([
        (1.0845, 1.0850, 1.0840, 1.0846),
        (1.0848, 1.0852, 1.0846, 1.0850),   # touches entry 1.0850 -> fill
        (1.0840, 1.0845, 1.0788, 1.0792),   # hits target 1.0790
    ])
    _process(t, cs, 1, 8)
    assert t.status == "open"
    _process(t, cs, 2, 8)
    assert t.status == "closed" and t.exit_reason == "target"
    assert t.realized_r == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# End-to-end backtest
# --------------------------------------------------------------------------- #
def test_backtest_long_setup_is_a_win():
    res = backtest(candles(LONG_SETUP), min_score=2, entry_mode="limit", warmup=6)
    assert res.stats()["trades"] >= 1
    assert res.closed[0].direction == "long"
    assert res.closed[0].realized_r > 0     # the setup expands to target
    assert len(res.equity_curve) == len(res.closed)


def test_backtest_stats_keys():
    res = backtest(candles(LONG_SETUP), min_score=2, warmup=6)
    st = res.stats()
    for k in ("trades", "win_rate", "total_r", "expectancy_r",
              "profit_factor", "max_drawdown_r"):
        assert k in st
