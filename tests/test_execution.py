"""Tests for the execution layer: PaperBroker, Trader, and safety guards."""

import pytest

from ictlib.execution import PaperBroker, Trader
from ictlib.execution.base import Broker, Account, OrderResult
from ictlib.models import Signal
from ictlib.risk import RiskParams
from ictlib.analysis import analyze
from ictlib.scanner import scan
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles
from datetime import datetime, timezone

TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _sig(direction="long", entry=1.0850, stop=1.0830, target=1.0910, score=5):
    return Signal(direction=direction, ts=TS, index=1, entry=entry,
                  entry_zone=(entry - 0.0005, entry + 0.0005), stop=stop,
                  targets=[target], reasons=[], score=score)


# --------------------------------------------------------------------------- #
# PaperBroker lifecycle
# --------------------------------------------------------------------------- #
def test_paper_limit_fills_then_takes_profit():
    b = PaperBroker(balance=10_000, pip=0.0001, pip_value=10.0)
    res = b.place_bracket("EUR_USD", "buy", 1.0, stop=1.0830, target=1.0910,
                          entry=1.0850, type="limit")
    assert res.ok
    # bar 1 touches the entry -> fills
    b.feed(candles([(1.0855, 1.0858, 1.0848, 1.0852)])[0])
    assert len(b.positions()) == 1 and b.positions()[0].status == "open"
    # bar 2 hits the take-profit
    b.feed(candles([(1.0860, 1.0912, 1.0858, 1.0908)])[0])
    p = b.positions()[0]
    assert p.status == "closed" and p.exit_reason == "target"
    # +60 pips * $10 * 1 lot = +$600
    assert p.pnl == pytest.approx(600.0)
    assert p.r == pytest.approx(3.0)
    assert b.account().balance == pytest.approx(10_600.0)


def test_paper_stop_out():
    b = PaperBroker(pip=0.0001, pip_value=10.0)
    b.place_bracket("EUR_USD", "buy", 1.0, stop=1.0830, target=1.0910,
                    entry=1.0850, type="limit")
    b.feed(candles([(1.0855, 1.0858, 1.0848, 1.0852)])[0])   # fill
    b.feed(candles([(1.0850, 1.0852, 1.0825, 1.0828)])[0])   # stop
    p = b.positions()[0]
    assert p.exit_reason == "stop" and p.pnl == pytest.approx(-200.0)


def test_paper_short_and_market_order():
    b = PaperBroker(pip=0.0001, pip_value=10.0)
    b.place_bracket("EUR_USD", "sell", 2.0, stop=1.0870, target=1.0790, type="market")
    b.feed(candles([(1.0850, 1.0855, 1.0845, 1.0848)])[0])   # market fills at open 1.0850
    assert b.positions()[0].entry_price == pytest.approx(1.0850)
    b.feed(candles([(1.0840, 1.0845, 1.0788, 1.0792)])[0])   # hits target 1.0790
    p = b.positions()[0]
    assert p.exit_reason == "target"
    # short 60 pips * $10 * 2 lots = +$1200
    assert p.pnl == pytest.approx(1200.0)


def test_paper_cancel():
    b = PaperBroker()
    r = b.place_bracket("EUR_USD", "buy", 1.0, stop=1.08, target=1.09, entry=1.085,
                        type="limit")
    assert b.cancel(r.id).ok
    assert b.orders()[0].status == "cancelled"


# --------------------------------------------------------------------------- #
# Trader
# --------------------------------------------------------------------------- #
def test_trader_dry_run_does_not_submit():
    b = PaperBroker()
    t = Trader(b, instrument="EUR_USD", pip=0.0001, dry_run=True, min_score=3)
    res = t.submit(_sig())
    assert res.ok and "dry-run" in res.message
    assert b.orders() == []                      # nothing sent


def test_trader_submits_to_paper():
    b = PaperBroker(pip=0.0001, pip_value=10.0)
    t = Trader(b, instrument="EUR_USD", pip=0.0001, dry_run=False, min_score=3,
               risk=RiskParams(equity=10_000, risk_pct=0.01))
    res = t.submit(_sig())
    assert res.ok
    o = b.orders()[0]
    assert o.side == "buy" and o.stop == 1.0830 and o.target == 1.0910
    # 1% of 10k = $100 risk, 20-pip SL, $10/pip -> 0.5 lots
    assert o.lots == pytest.approx(0.5, rel=1e-3)


def test_trader_dedup_and_min_score():
    b = PaperBroker()
    t = Trader(b, instrument="EUR_USD", pip=0.0001, dry_run=False, min_score=5)
    assert t.submit(_sig(score=3)) is None       # below min score
    assert t.submit(_sig(score=6)) is not None
    assert t.submit(_sig(score=6)) is None        # same index -> deduped


def test_trader_refuses_live_without_allow():
    class FakeLive(Broker):
        live = True
        def account(self): return Account(0, 0)
        def place_bracket(self, *a, **k): return OrderResult(True)
        def positions(self): return []
        def orders(self): return []

    with pytest.raises(PermissionError):
        Trader(FakeLive(), instrument="EUR_USD", pip=0.0001, dry_run=False)
    # dry_run or allow_live is fine
    Trader(FakeLive(), instrument="EUR_USD", pip=0.0001, dry_run=True)
    Trader(FakeLive(), instrument="EUR_USD", pip=0.0001, dry_run=False, allow_live=True)


# --------------------------------------------------------------------------- #
# end-to-end: scan -> trade -> simulate
# --------------------------------------------------------------------------- #
def test_scan_to_paper_roundtrip():
    cs = candles(LONG_SETUP)
    sigs = scan(analyze(cs), min_score=2)
    b = PaperBroker(pip=0.0001, pip_value=10.0)
    t = Trader(b, instrument="EUR_USD", pip=0.0001, dry_run=False, min_score=2)
    t.process(sigs)
    for c in cs:
        b.feed(c)
    # an account object is always available and orders were placed
    assert isinstance(b.account(), Account)
    assert len(b.orders()) >= 1
