"""Generate a longer synthetic EUR/USD M15 series for the backtester by
stitching winning and losing variants of the canonical long setup at varying
price levels. Purely illustrative — deterministic, not real market data.

Run: python examples/generate_backtest_data.py
Writes sample_data/EUR_USD_M15_backtest.csv and prints backtest stats.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from ictlib.models import Candle
from ictlib.data import save_csv
from ictlib.backtest import backtest, BacktestResult
from ictlib.risk import RiskParams
from ictlib.sample_setups import LONG_SETUP

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A losing variant: same sweep + MSS, but price then fails back through the stop.
LOSS_SETUP = LONG_SETUP[:16] + [
    (1.08560, 1.08600, 1.08500, 1.08520),   # n+1 keeps the FVG (low 1.0850 > 1.0830)
    (1.08520, 1.08560, 1.08320, 1.08340),
    (1.08340, 1.08360, 1.08060, 1.08080),
    (1.08080, 1.08100, 1.07980, 1.08000),   # trades below sweep low -> stop hit
    (1.08000, 1.08040, 1.07960, 1.08010),
    (1.08010, 1.08060, 1.07980, 1.08020),
]


def _offset(rows, delta):
    return [(o + delta, h + delta, l + delta, c + delta) for o, h, l, c in rows]


def build():
    # Alternate win/loss blocks, each at its own price level (monotonic offsets so
    # each forms a fresh local range), separated by a flat reset so the previous
    # block's structure ages out of the growing analysis window.
    plan = [("win", 0.000), ("loss", 0.012), ("win", 0.026), ("loss", 0.040),
            ("win", 0.055), ("loss", 0.069), ("win", 0.084), ("win", 0.098)]
    rows = []
    for kind, delta in plan:
        block = LONG_SETUP if kind == "win" else LOSS_SETUP
        rows += _offset(block, delta)
        last = rows[-1][3]
        rows += [(last, last + 0.0004, last - 0.0004, last)] * 6  # reset segment
    return rows


def _block_candles(rows, delta, base):
    return [Candle(base + timedelta(minutes=15 * i), *[v + delta for v in r], 1000)
            for i, r in enumerate(rows)]


def main():
    # A sequence of independent setups (each a fresh scenario) so cross-block
    # analysis context doesn't mask detections — a clean mix for the equity curve.
    plan = [("win", 0.0), ("loss", 0.004), ("win", 0.008), ("win", 0.002),
            ("loss", 0.010), ("win", 0.006), ("loss", 0.012), ("win", 0.014),
            ("win", 0.003), ("loss", 0.009)]
    risk = RiskParams(equity=10_000, risk_pct=0.01)

    # also write a continuous CSV so the CLI --backtest has something to read
    rows = build()
    base = datetime(2026, 8, 3, 8, 0, tzinfo=timezone.utc)
    save_csv(os.path.join(HERE, "sample_data", "EUR_USD_M15_backtest.csv"),
             [Candle(base + timedelta(minutes=15 * i), *r, 1000)
              for i, r in enumerate(rows)])

    agg = BacktestResult()
    for k, (kind, delta) in enumerate(plan):
        block = LONG_SETUP if kind == "win" else LOSS_SETUP
        cs = _block_candles(block, delta, base + timedelta(days=k))
        r = backtest(cs, min_score=2, entry_mode="limit", risk=risk, warmup=6)
        agg.trades.extend(r.closed)

    cum = 0.0
    for t in sorted(agg.trades, key=lambda x: (x.exit_index or 0)):
        cum += t.realized_r
        agg.equity_curve.append(round(cum, 4))

    print("stats:", agg.stats())
    print("equity curve (cumulative R):", agg.equity_curve)
    print(f"\n{len(agg.closed)} closed trades:")
    for t in agg.closed:
        print(f"  {t.direction} {t.exit_reason:7} R={t.realized_r:+.2f}  score={t.score}")

    # render the equity curve
    from ictlib.viz import render_equity_html
    path = os.path.join(HERE, "examples", "backtest_equity.html")
    render_equity_html(agg, path, title="ICT Scanner — Backtest (synthetic)")
    print(f"\nequity curve chart -> {path}")


if __name__ == "__main__":
    main()
