"""Tests for the HistData loader and the backtester's lookback window."""

from datetime import timezone

from ictlib.data.csv_loader import load_histdata
from ictlib.backtest import backtest
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


def test_load_histdata(tmp_path):
    p = tmp_path / "gold.csv"
    p.write_text(
        "20090315 170000;929.60;929.60;929.60;929.60;0\n"
        "20090315 180100;925.80;927.30;925.80;925.90;0\n"
    )
    cs = load_histdata(str(p))
    assert len(cs) == 2
    # 17:00 EST (UTC-5) -> 22:00 UTC
    assert cs[0].ts.astimezone(timezone.utc).hour == 22
    assert cs[0].open == 929.60 and cs[1].high == 927.30
    assert cs[0].ts.tzinfo is not None            # tz-aware


def test_backtest_lookback_matches_full_on_small_series():
    cs = candles(LONG_SETUP)
    full = backtest(cs, min_score=2, warmup=6)
    win = backtest(cs, min_score=2, warmup=6, lookback=len(cs))
    assert full.stats()["trades"] == win.stats()["trades"]


def test_backtest_lookback_absolute_indices():
    # with a small lookback the trade's signal_index must be an absolute index
    cs = candles(LONG_SETUP)
    res = backtest(cs, min_score=2, warmup=6, lookback=12)
    for t in res.trades:
        assert 0 <= t.signal_index < len(cs)
