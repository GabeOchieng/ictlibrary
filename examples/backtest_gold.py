"""Backtest the ICT scanner on a HistData.com DAT_ASCII M1 file (e.g. XAUUSD).

Download a year of M1 data from https://www.histdata.com (ASCII / M1), then:

    python examples/backtest_gold.py path/to/DAT_ASCII_XAUUSD_M1_2009.csv

Resamples M1 -> M15, runs a walk-forward backtest (no lookahead), prints the
stats, and writes an equity-curve chart + an annotated chart of a recent window.
"""

from __future__ import annotations

import os
import sys

from ictlib.data import load_histdata
from ictlib.mtf import resample_tf
from ictlib.backtest import backtest
from ictlib.risk import RiskParams
from ictlib.analysis import analyze
from ictlib.scanner import scan
from ictlib.viz import render_equity_html, render_html

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(path: str, symbol: str = "XAU/USD", min_score: int = 3):
    m1 = load_histdata(path)
    m15 = resample_tf(m1, 15)
    print(f"{len(m1)} M1 bars -> {len(m15)} M15 bars "
          f"({m15[0].ts.date()} .. {m15[-1].ts.date()})")

    res = backtest(m15, instrument=symbol.replace("/", "_"),
                   risk=RiskParams(equity=10_000, risk_pct=0.01),
                   min_score=min_score, entry_mode="limit", lookback=300)
    print("stats:", res.stats())

    eq = os.path.join(HERE, "examples", "gold_equity.html")
    render_equity_html(res, eq, title=f"{symbol} M15 — Backtest (min score {min_score})")

    a = analyze(m15[-220:], htf_timeframes=[60, 240])
    sigs = scan(a, min_score=min_score)
    chart = os.path.join(HERE, "examples", "gold_chart.html")
    render_html(a, chart, title=f"{symbol} M15 (real data)", instrument=symbol,
                granularity="M15", signals=sigs)
    print(f"charts -> {eq}\n         {chart}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python examples/backtest_gold.py <histdata_m1.csv>")
    main(sys.argv[1])
