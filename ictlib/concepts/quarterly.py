"""Quarterly Theory and Power of Three (concepts/22-quarterly-theory,
concepts/12-power-of-three).

True Day Open (TDO) = the 00:00 NY price — the primary intraday premium/discount
reference. The day splits into four quarters that carry the AMD-X phases:

    Q1  18:00-00:00 NY   accumulation
    Q2  00:00-06:00 NY   manipulation (Judas)
    Q3  06:00-12:00 NY   distribution (the true move)
    Q4  12:00-18:00 NY   continuation / reversal
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from ..models import Candle, QuarterlyContext
from .killzones import ny_minutes
from .sessions import _ny_date

# (quarter, start_min, end_min, phase) — Q1 wraps from 18:00 to midnight
_QUARTERS = [
    ("Q1", 18 * 60, 24 * 60, "accumulation"),
    ("Q2", 0, 6 * 60, "manipulation"),
    ("Q3", 6 * 60, 12 * 60, "distribution"),
    ("Q4", 12 * 60, 18 * 60, "continuation/reversal"),
]


def daily_quarter(ts: datetime) -> Tuple[str, str]:
    """Return (quarter, AMD phase) for a timestamp's NY time."""
    m = ny_minutes(ts)
    for q, start, end, phase in _QUARTERS:
        if start <= m < end:
            return q, phase
    return "Q1", "accumulation"  # 18:00-24:00 already covered; safety net


def true_day_open(candles: List[Candle]) -> Tuple[Optional[float], Optional[int]]:
    """TDO = open of the first candle of the most recent NY date (00:00 NY)."""
    if not candles:
        return None, None
    last_date = _ny_date(candles[-1].ts)
    for i, c in enumerate(candles):
        if _ny_date(c.ts) == last_date:
            return c.open, i
    return None, None


def quarterly_context(candles: List[Candle]) -> QuarterlyContext:
    if not candles:
        return QuarterlyContext()
    tdo, tdo_i = true_day_open(candles)
    q, phase = daily_quarter(candles[-1].ts)
    price_vs = None
    if tdo is not None:
        close = candles[-1].close
        price_vs = "premium" if close > tdo else "discount" if close < tdo else "at"
    return QuarterlyContext(
        tdo=tdo, tdo_index=tdo_i, daily_quarter=q, phase=phase, price_vs_tdo=price_vs,
    )


def ninety_minute_cycle(ts: datetime) -> Tuple[int, str, str]:
    """The 90-minute micro-cycle and its 22.5-min mini-quarter AMD phase
    (concepts/04-time-cycles/90-minute-cycle). Cycles are NY-time anchored to
    the 6-hour session quarters; each splits into four 22.5-min mini-quarters."""
    m = ny_minutes(ts)
    q_start = (int(m) // 360) * 360          # 6-hour session quarter start
    into_q = m - q_start
    cycle = int(into_q // 90) + 1            # which 90-min cycle (1..4)
    into_cycle = into_q - (cycle - 1) * 90
    mini = int(into_cycle // 22.5) + 1       # which 22.5-min mini-quarter (1..4)
    phase = ["accumulation", "manipulation", "distribution", "continuation/reversal"][mini - 1]
    return cycle, f"Q{mini}", phase


def po3_phase(candles: List[Candle]) -> Optional[str]:
    """The current Power-of-Three phase, via the Quarterly-Theory time mapping."""
    if not candles:
        return None
    return daily_quarter(candles[-1].ts)[1]
