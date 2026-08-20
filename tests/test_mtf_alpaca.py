"""Tests for multi-timeframe HTF bias and the Alpaca data client."""

from datetime import datetime, timedelta, timezone

import pytest

from ictlib.models import Candle
from ictlib.mtf import (
    resample_tf, infer_tf_minutes, tf_label, multi_timeframe_bias, timeframe_read,
)
from ictlib.analysis import analyze
from ictlib.scanner import scan
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


def _series(rows, minutes=15, base=datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)):
    return [Candle(base + timedelta(minutes=minutes * i), *r, 1000)
            for i, r in enumerate(rows)]


def _rising_zigzag(cycles=4):
    """A net-rising series with deep pullbacks whose legs survive resampling to
    H1/H4 (so fractal swings and bullish BOS form there), ending on a fresh
    higher high so the most recent break is bullish. A monotonic staircase — or a
    zigzag whose legs are shorter than the HTF bucket — has no swings once
    resampled."""
    rows = []
    price = 1.00
    for _ in range(cycles):
        for _ in range(20):                                  # 20 up bars
            rows.append((price, price + 0.004, price - 0.001, price + 0.003))
            price += 0.003
        for _ in range(12):                                  # 12 down bars (pullback)
            rows.append((price, price + 0.001, price - 0.004, price - 0.003))
            price -= 0.003
    for _ in range(20):                                      # trailing up-leg
        rows.append((price, price + 0.004, price - 0.001, price + 0.003))
        price += 0.003
    return rows


# --------------------------------------------------------------------------- #
# resample / tf helpers
# --------------------------------------------------------------------------- #
def test_resample_aggregates_ohlc():
    # four 15-min bars -> one H1 bar with proper OHLC
    base = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
    rows = [(1.00, 1.02, 0.99, 1.01), (1.01, 1.05, 1.00, 1.03),
            (1.03, 1.04, 0.98, 1.02), (1.02, 1.06, 1.01, 1.055)]
    cs = [Candle(base + timedelta(minutes=15 * i), *r, 10) for i, r in enumerate(rows)]
    h1 = resample_tf(cs, 60)
    assert len(h1) == 1
    b = h1[0]
    assert b.open == pytest.approx(1.00)     # first open
    assert b.high == pytest.approx(1.06)     # max high
    assert b.low == pytest.approx(0.98)      # min low
    assert b.close == pytest.approx(1.055)   # last close
    assert b.volume == pytest.approx(40)


def test_infer_tf_and_label():
    cs = candles(LONG_SETUP)              # 15-min spacing
    assert infer_tf_minutes(cs) == 15
    assert tf_label(60) == "H1" and tf_label(240) == "H4"


def test_timeframe_read_none_when_too_few():
    assert timeframe_read(candles(LONG_SETUP)[:3], 60) is None


# --------------------------------------------------------------------------- #
# aggregate bias
# --------------------------------------------------------------------------- #
def test_mtf_bias_bullish_uptrend():
    cs = _series(_rising_zigzag())
    ctx = multi_timeframe_bias(cs, htf_minutes=[60, 240])
    assert ctx.entry_minutes == 15
    assert [r.label for r in ctx.reads] == ["H4", "H1"]   # highest first
    assert ctx.bias == "bullish"
    assert ctx.aligned("long") and not ctx.aligned("short")


def test_mtf_skips_lower_or_equal_tf():
    ctx = multi_timeframe_bias(candles(LONG_SETUP), htf_minutes=[5, 15])
    assert ctx.reads == []           # nothing higher than the 15m entry TF
    assert ctx.bias == "neutral"


# --------------------------------------------------------------------------- #
# analyze + scan integration
# --------------------------------------------------------------------------- #
def test_analyze_with_htf_and_require_alignment():
    cs = _series(_rising_zigzag())
    a = analyze(cs, htf_timeframes=[60, 240])
    assert a.mtf is not None
    su = a.summary()
    assert su["htf_bias"] in ("bullish", "bearish", "neutral")
    # require_htf_alignment must not raise and returns a list
    assert isinstance(scan(a, min_score=2, require_htf_alignment=True), list)


# --------------------------------------------------------------------------- #
# Alpaca client (offline: construction + timeframe mapping only)
# --------------------------------------------------------------------------- #
def test_alpaca_requires_credentials(monkeypatch):
    from ictlib.data.alpaca import AlpacaClient, AlpacaError
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    with pytest.raises(AlpacaError):
        AlpacaClient()


def test_cli_htf_minutes_parsing():
    from ictlib.cli import _htf_minutes
    assert _htf_minutes("H1,H4") == [60, 240]
    assert _htf_minutes("h1, 30") == [60, 30]   # label + raw minutes, case-insensitive


def test_alpaca_timeframe_map():
    from ictlib.data.alpaca import _TF
    assert _TF["M15"] == "15Min" and _TF["H4"] == "4Hour" and _TF["D"] == "1Day"


def test_alpaca_client_constructs_with_keys():
    from ictlib.data.alpaca import AlpacaClient
    c = AlpacaClient(key_id="k", secret_key="s", feed="iex")
    assert c._headers()["APCA-API-KEY-ID"] == "k"
    assert c.feed == "iex"
