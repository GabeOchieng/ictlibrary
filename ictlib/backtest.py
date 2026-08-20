"""Walk-forward backtester for the ICT scanner.

At each bar it re-runs ``analyze`` on the candles seen *so far* (no lookahead),
registers any newly-confirmed signal as a pending trade, then simulates fills,
stops and targets bar-by-bar. Results are reported in R multiples so they are
comparable across instruments and SL sizes (concepts/32-risk-management).

Modelling choices (stated so results are honest):
- Entry is a limit at the signal's entry price; it fills when a later bar trades
  through that price, within ``entry_expiry`` bars, else the signal is cancelled.
- Within a bar, the stop is checked before the target (worst-case fill).
- TP is the signal's chosen target (default the furthest — the runner/DOL).
- Unclosed trades at the end are marked to market at the last close.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .models import Candle
from .analysis import analyze
from .scanner import scan
from .risk import RiskParams, position_size, r_multiple, pips


@dataclass
class Trade:
    direction: str            # "long" | "short"
    signal_index: int
    detected_index: int
    entry: float
    stop: float
    target: float
    lots: float
    score: int
    status: str = "pending"   # pending | open | closed | cancelled
    entry_index: Optional[int] = None
    exit_index: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    realized_r: float = 0.0

    def to_dict(self) -> dict:
        return {
            "direction": self.direction, "signal_index": self.signal_index,
            "entry": self.entry, "stop": self.stop, "target": self.target,
            "status": self.status, "exit_reason": self.exit_reason,
            "realized_r": round(self.realized_r, 3), "score": self.score,
        }


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)  # cumulative R

    @property
    def closed(self) -> List[Trade]:
        return [t for t in self.trades if t.status == "closed"]

    def stats(self) -> dict:
        cl = self.closed
        n = len(cl)
        if n == 0:
            return {"trades": 0}
        wins = [t for t in cl if t.realized_r > 0]
        losses = [t for t in cl if t.realized_r <= 0]
        total_r = sum(t.realized_r for t in cl)
        gross_win = sum(t.realized_r for t in wins)
        gross_loss = -sum(t.realized_r for t in losses)
        peak = 0.0
        cum = 0.0
        max_dd = 0.0
        for t in sorted(cl, key=lambda x: (x.exit_index or 0)):
            cum += t.realized_r
            peak = max(peak, cum)
            max_dd = max(max_dd, peak - cum)
        return {
            "trades": n,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / n, 3),
            "total_r": round(total_r, 2),
            "expectancy_r": round(total_r / n, 3),
            "avg_win_r": round(gross_win / len(wins), 2) if wins else 0.0,
            "avg_loss_r": round(-gross_loss / len(losses), 2) if losses else 0.0,
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else float("inf"),
            "max_drawdown_r": round(max_dd, 2),
        }


def backtest(
    candles: List[Candle],
    *,
    instrument: str = "EUR_USD",
    pip: Optional[float] = None,
    risk: Optional[RiskParams] = None,
    min_score: int = 3,
    target_index: int = -1,     # which signal target to use as TP (-1 = furthest)
    entry_expiry: int = 8,      # bars a pending entry stays live
    entry_mode: str = "limit",  # "limit" (fill at entry price) | "market" (fill on confirm)
    warmup: int = 8,
    lookback: Optional[int] = None,     # analyse only the last N bars each step (speed)
    htf_timeframes: Optional[List[int]] = None,
) -> BacktestResult:
    from .concepts import infer_pip_size
    if pip is None:
        pip = infer_pip_size(candles)
    risk = risk or RiskParams()

    trades: List[Trade] = []
    live: List[Trade] = []
    seen: set[int] = set()

    for i in range(warmup, len(candles)):
        # 1) manage existing trades against bar i (they were detected earlier)
        for t in list(live):
            _process(t, candles, i, entry_expiry)
        live = [t for t in live if t.status in ("pending", "open")]

        # 2) detect newly-confirmed signals on the data seen so far (optionally
        #    only the last ``lookback`` bars, to keep large backtests O(n·W)).
        offset = max(0, i + 1 - lookback) if lookback else 0
        a = analyze(candles[offset: i + 1], htf_timeframes=htf_timeframes)
        for s in scan(a, min_score=min_score):
            abs_index = offset + s.index
            if abs_index in seen or not s.targets:
                continue
            seen.add(abs_index)
            entry = s.entry if entry_mode == "limit" else candles[i].close
            # keep only targets that are genuine profit targets beyond the entry
            valid = [t for t in s.targets
                     if (t > entry) == (s.direction == "long")]
            if not valid:
                continue
            target = valid[target_index]
            lots = position_size(entry, s.stop, pip, risk)
            t = Trade(
                direction=s.direction, signal_index=abs_index, detected_index=i,
                entry=entry, stop=s.stop, target=target, lots=lots, score=s.score,
            )
            if entry_mode == "market":       # fills immediately on confirmation
                t.status, t.entry_index = "open", i
            trades.append(t)
            live.append(t)

    # 3) finalise anything still open at the last bar
    last = len(candles) - 1
    for t in live:
        if t.status == "open":
            _close(t, last, candles[last].close, "eod")
        else:
            t.status = "cancelled"

    result = BacktestResult(trades=trades)
    cum = 0.0
    for t in sorted(result.closed, key=lambda x: (x.exit_index or 0)):
        cum += t.realized_r
        result.equity_curve.append(round(cum, 4))
    return result


def _process(t: Trade, candles: List[Candle], i: int, entry_expiry: int) -> None:
    if i <= t.detected_index:
        return
    bar = candles[i]
    if t.status == "pending":
        if bar.low <= t.entry <= bar.high:      # entry touched -> fill
            t.status, t.entry_index = "open", i
        elif i - t.detected_index >= entry_expiry:
            t.status = "cancelled"
        return
    if t.status == "open":
        if t.direction == "long":
            if bar.low <= t.stop:               # stop first (worst case)
                _close(t, i, t.stop, "stop")
            elif bar.high >= t.target:
                _close(t, i, t.target, "target")
        else:
            if bar.high >= t.stop:
                _close(t, i, t.stop, "stop")
            elif bar.low <= t.target:
                _close(t, i, t.target, "target")


def _close(t: Trade, i: int, price: float, reason: str) -> None:
    t.status = "closed"
    t.exit_index = i
    t.exit_price = price
    t.exit_reason = reason
    t.realized_r = r_multiple(t.entry, t.stop, price)
