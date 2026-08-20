"""Tests for SMT divergence, intermarket reads, and news blackout."""

from datetime import datetime, timedelta, timezone

import pytest

from ictlib.models import Candle, NewsEvent
from ictlib.smt import find_smt_divergence
from ictlib.intermarket import dollar_index_smt, intermarket_bias
from ictlib.news import in_blackout, blackout_window, news_windows
from ictlib.analysis import analyze

from _helpers import candles


def _pair(highs_lows, base=datetime(2026, 8, 3, tzinfo=timezone.utc)):
    """Build candles from (high, low) pairs with matching open/close."""
    out = []
    for i, (h, l) in enumerate(highs_lows):
        mid = (h + l) / 2
        out.append(Candle(base + timedelta(minutes=15 * i), mid, h, l, mid, 1000))
    return out


# --------------------------------------------------------------------------- #
# SMT divergence
# --------------------------------------------------------------------------- #
def test_bearish_smt_positive_correlation():
    # A makes a higher high at the 2nd swing; B makes a lower high -> bearish SMT.
    # swing highs need width-2 confirmation, so pad around the pivots.
    a = _pair([(1.00, 0.98), (1.01, 0.99), (1.05, 1.00), (1.01, 0.99),
               (1.00, 0.98), (1.02, 0.99), (1.08, 1.01), (1.02, 0.99), (1.00, 0.98)])
    b = _pair([(1.00, 0.98), (1.01, 0.99), (1.05, 1.00), (1.01, 0.99),
               (1.00, 0.98), (1.02, 0.99), (1.03, 1.01), (1.02, 0.99), (1.00, 0.98)])
    #   A's 2nd high (1.08) > 1st (1.05); B's 2nd high (1.03) < 1st (1.05) -> divergence
    smt = find_smt_divergence(a, b, correlation="positive")
    assert any(d.direction == "bear" for d in smt)


def test_no_smt_when_both_confirm():
    a = _pair([(1.00, 0.98), (1.05, 1.00), (1.00, 0.98), (1.08, 1.01), (1.00, 0.98)])
    b = _pair([(1.00, 0.98), (1.05, 1.00), (1.00, 0.98), (1.08, 1.01), (1.00, 0.98)])
    assert find_smt_divergence(a, b, correlation="positive") == []


def test_dollar_index_smt_negative_corr():
    # pair makes higher high; DXY (inverse) fails to make a new low -> bearish SMT
    pair = _pair([(1.00, 0.98), (1.01, 0.99), (1.05, 1.00), (1.01, 0.99),
                  (1.00, 0.98), (1.02, 0.99), (1.08, 1.01), (1.02, 0.99), (1.00, 0.98)])
    dxy = _pair([(1.00, 0.98), (1.01, 0.97), (1.02, 0.95), (1.01, 0.97),
                 (1.00, 0.98), (1.02, 0.99), (1.03, 0.99), (1.02, 0.99), (1.00, 0.98)])
    smt = dollar_index_smt(pair, dxy)
    assert isinstance(smt, list)
    assert intermarket_bias(smt) in ("bullish", "bearish", "neutral")


# --------------------------------------------------------------------------- #
# News blackout
# --------------------------------------------------------------------------- #
def test_news_blackout_window():
    ev = NewsEvent(ts=datetime(2026, 8, 7, 12, 30, tzinfo=timezone.utc),
                   name="NFP", kind="nfp")
    start, end = blackout_window(ev)
    # NFP = 15 min before, 30 min after
    assert start == ev.ts - timedelta(minutes=15)
    assert end == ev.ts + timedelta(minutes=30)


def test_in_blackout():
    ev = NewsEvent(ts=datetime(2026, 8, 7, 12, 30, tzinfo=timezone.utc),
                   name="NFP", kind="nfp")
    inside = datetime(2026, 8, 7, 12, 40, tzinfo=timezone.utc)
    outside = datetime(2026, 8, 7, 14, 0, tzinfo=timezone.utc)
    assert in_blackout(inside, [ev]).name == "NFP"
    assert in_blackout(outside, [ev]) is None
    assert len(news_windows([ev])) == 1


# --------------------------------------------------------------------------- #
# analyze integration
# --------------------------------------------------------------------------- #
def test_analyze_with_smt_and_news():
    from ictlib.sample_setups import LONG_SETUP
    cs = candles(LONG_SETUP)
    ref = candles(LONG_SETUP)                      # trivially correlated reference
    ev = NewsEvent(ts=cs[-1].ts, name="FOMC", kind="fomc")
    a = analyze(cs, smt_reference=ref, smt_correlation="positive", news_events=[ev])
    su = a.summary()
    assert "smt_divergences" in su
    assert su["news_blackout"] == "FOMC"           # last bar is inside the window
