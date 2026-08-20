"""Rejection blocks (concepts/19-rejection-blocks/rejection-block).

A candle with a long wick (>= 60% of range) that rejects a key level. Unlike
order blocks (body-based), the rejected WICK is the zone.

    bullish RB: long lower wick, close near the top   → support, zone [low, body_low]
    bearish RB: long upper wick, close near the bottom → resistance, zone [body_high, high]

``key_levels`` (optional) restricts detection to wicks whose tip reaches a known
level (swing / pool / FVG edge) within ``tol`` — the "reaches a key level" rule.
"""

from __future__ import annotations

from typing import List, Optional

from ..models import Candle, RejectionBlock


def find_rejection_blocks(
    candles: List[Candle],
    *,
    min_wick: float = 0.60,
    close_frac: float = 0.40,
    key_levels: Optional[List[float]] = None,
    tol: float = 0.0,
) -> List[RejectionBlock]:
    out: List[RejectionBlock] = []
    for i, c in enumerate(candles):
        if c.range <= 0:
            continue
        lw = c.lower_wick / c.range
        uw = c.upper_wick / c.range

        # bullish RB: long lower wick, close in the top close_frac of the range
        if lw >= min_wick and c.close >= c.low + (1 - close_frac) * c.range:
            if _near(c.low, key_levels, tol):
                rb = RejectionBlock(i, c.ts, "bull", c.low, c.body_low, lw)
                _mark(rb, candles)
                out.append(rb)
                continue
        # bearish RB: long upper wick, close in the bottom close_frac of the range
        if uw >= min_wick and c.close <= c.low + close_frac * c.range:
            if _near(c.high, key_levels, tol):
                rb = RejectionBlock(i, c.ts, "bear", c.body_high, c.high, uw)
                _mark(rb, candles)
                out.append(rb)
    return out


def _near(price: float, levels: Optional[List[float]], tol: float) -> bool:
    if not levels:
        return True  # no filter -> accept all
    return any(abs(price - lv) <= tol for lv in levels)


def _mark(rb: RejectionBlock, candles: List[Candle]) -> None:
    for i in range(rb.index + 1, len(candles)):
        c = candles[i]
        if rb.direction == "bull" and c.low <= rb.high:
            rb.mitigated, rb.mitigated_index = True, i
            return
        if rb.direction == "bear" and c.high >= rb.low:
            rb.mitigated, rb.mitigated_index = True, i
            return
