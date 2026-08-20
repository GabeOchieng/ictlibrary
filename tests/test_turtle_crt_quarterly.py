"""Tests for Turtle Soup, CRT, Quarterly Theory / Power of Three."""

from datetime import datetime, timedelta, timezone

import pytest

from ictlib.models import Candle
from ictlib.concepts.turtle_soup import find_turtle_soups
from ictlib.concepts.quarterly import (
    daily_quarter, true_day_open, quarterly_context, po3_phase,
)
from ictlib.concepts.crt import find_crt_setups
from ictlib.concepts.liquidity import find_pools, find_sweeps
from ictlib.concepts.structure import find_swings
from ictlib.analysis import analyze
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


# --------------------------------------------------------------------------- #
# Turtle Soup
# --------------------------------------------------------------------------- #
def test_turtle_soup_on_setup():
    cs = candles(LONG_SETUP)
    sw = find_sweeps(cs, find_pools(find_swings(cs), pip=0.0001))
    ts = find_turtle_soups(cs, sw)
    # the SSL sweep in the long setup reverses up with displacement -> bullish TS
    assert any(t.direction == "bull" for t in ts)


def test_no_turtle_soup_without_reversal():
    # a sweep with no reversal displacement afterwards
    rows = [(1.10, 1.11, 1.09, 1.10), (1.10, 1.11, 1.08, 1.09),
            (1.09, 1.10, 1.06, 1.085),                    # swing low 1.06
            (1.085, 1.10, 1.083, 1.095), (1.095, 1.11, 1.09, 1.10),
            (1.10, 1.105, 1.04, 1.098),                   # sweep low
            (1.098, 1.099, 1.096, 1.0975),                # no displacement
            (1.0975, 1.0985, 1.096, 1.097)]
    cs = candles(rows)
    sw = find_sweeps(cs, find_pools(find_swings(cs), pip=0.0001))
    ts = find_turtle_soups(cs, sw, confirm_within=2)
    assert ts == []


# --------------------------------------------------------------------------- #
# Quarterly Theory / TDO / PO3
# --------------------------------------------------------------------------- #
def test_daily_quarters():
    # NY EDT = UTC-4 (August)
    assert daily_quarter(datetime(2026, 8, 20, 23, tzinfo=timezone.utc))[0] == "Q1"  # 19:00 NY
    assert daily_quarter(datetime(2026, 8, 20, 5, tzinfo=timezone.utc)) == ("Q2", "manipulation")   # 01:00 NY
    assert daily_quarter(datetime(2026, 8, 20, 13, tzinfo=timezone.utc)) == ("Q3", "distribution")  # 09:00 NY
    assert daily_quarter(datetime(2026, 8, 20, 20, tzinfo=timezone.utc)) == ("Q4", "continuation/reversal")  # 16:00 NY


def test_true_day_open():
    # first candle of the most recent NY date is the TDO
    base = datetime(2026, 8, 20, 4, tzinfo=timezone.utc)  # 00:00 NY
    cs = [Candle(base + timedelta(hours=h), 1.0800 + h * 0.001,
                 1.0810 + h * 0.001, 1.0790 + h * 0.001, 1.0805 + h * 0.001)
          for h in range(6)]
    tdo, idx = true_day_open(cs)
    assert idx == 0
    assert tdo == pytest.approx(1.0800)


def test_price_vs_tdo():
    base = datetime(2026, 8, 20, 4, tzinfo=timezone.utc)
    cs = [Candle(base, 1.0800, 1.0810, 1.0790, 1.0805),
          Candle(base + timedelta(hours=1), 1.0805, 1.0860, 1.0800, 1.0850)]
    q = quarterly_context(cs)
    assert q.tdo == pytest.approx(1.0800)
    assert q.price_vs_tdo == "premium"      # last close 1.0850 > TDO 1.0800
    assert q.phase == po3_phase(cs)


# --------------------------------------------------------------------------- #
# CRT
# --------------------------------------------------------------------------- #
def test_crt_setup_detects_sweep_of_htf_bound():
    # Two H1 reference candles (60 min each = 4x M15), then a bar sweeping the low.
    base = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    cs = []
    # ref hour 1: range 1.0800-1.0850
    for k in range(4):
        cs.append(Candle(base + timedelta(minutes=15 * k), 1.0820, 1.0850, 1.0800, 1.0830))
    # next hour: a bar sweeps below 1.0800 then closes back inside
    cs.append(Candle(base + timedelta(minutes=60), 1.0810, 1.0815, 1.0780, 1.0812))
    cs += [Candle(base + timedelta(minutes=60 + 15 * k), 1.0812, 1.0820, 1.0805, 1.0815)
           for k in range(1, 4)]
    setups = find_crt_setups(cs, htf_minutes=60)
    assert any(s.direction == "bull" and s.target == pytest.approx(1.0850)
               for s in setups)


# --------------------------------------------------------------------------- #
# analysis integration
# --------------------------------------------------------------------------- #
def test_analysis_exposes_quarterly_and_turtle():
    a = analyze(candles(LONG_SETUP))
    su = a.summary()
    assert "turtle_soups" in su and "phase" in su and "quarter" in su
    assert a.quarterly is not None
    assert a.quarterly.phase in ("accumulation", "manipulation",
                                 "distribution", "continuation/reversal")
