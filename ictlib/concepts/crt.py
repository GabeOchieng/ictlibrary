"""Candle Range Theory (concepts/21-crt).

NOTE: CRT is *community-attributed* (Romeo / TTrades, 2024), not ICT-original —
ICT stated it is "based on my ideas but not my concept". Implemented for
completeness and disambiguation.

A HTF reference candle defines a range [low, high]. A later bar that sweeps one
bound and closes back inside predicts a reversal toward the opposite bound.
"""

from __future__ import annotations

from datetime import timezone
from typing import List

from ..models import Candle, CRTSetup


def _buckets(candles: List[Candle], period_minutes: int):
    """Yield (start_index, end_index, high, low) per HTF period bucket."""
    if not candles:
        return
    period = period_minutes * 60
    cur_key = None
    start = 0
    hi = lo = None
    for i, c in enumerate(candles):
        key = int(c.ts.astimezone(timezone.utc).timestamp() // period)
        if cur_key is None:
            cur_key, start, hi, lo = key, i, c.high, c.low
        elif key != cur_key:
            yield (start, i - 1, hi, lo)
            cur_key, start, hi, lo = key, i, c.high, c.low
        else:
            hi, lo = max(hi, c.high), min(lo, c.low)
    yield (start, len(candles) - 1, hi, lo)


def find_crt_setups(
    candles: List[Candle],
    *,
    htf_minutes: int = 240,   # H4 reference candles by default
    max_setups: int = 12,
) -> List[CRTSetup]:
    """Detect CRT setups: a completed HTF candle whose bound a later bar sweeps."""
    buckets = list(_buckets(candles, htf_minutes))
    out: List[CRTSetup] = []
    for (start, end, hi, lo) in buckets[:-1]:      # skip the still-forming last bucket
        for j in range(end + 1, len(candles)):
            c = candles[j]
            if c.high > hi and c.close < hi:       # swept the high -> reverse down
                out.append(CRTSetup(start, end, hi, lo, "bear", j, lo))
                break
            if c.low < lo and c.close > lo:        # swept the low -> reverse up
                out.append(CRTSetup(start, end, hi, lo, "bull", j, hi))
                break
    return out[-max_setups:]
