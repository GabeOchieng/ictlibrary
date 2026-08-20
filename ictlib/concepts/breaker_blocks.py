"""Breaker blocks (concepts/08-breaker-blocks/breaker-block).

A breaker is an order block that failed in its original direction — price closed
through the OB body against it, with displacement — and now flips polarity:

    failed bullish OB → bearish breaker (resistance): close < OB_low  + bear displacement
    failed bearish OB → bullish breaker (support):    close > OB_high + bull displacement

The OB body becomes the breaker zone in the new direction; the meaningful state
is whether price has since *retested* it (the entry trigger).
"""

from __future__ import annotations

from typing import List

from ..models import Candle, OrderBlock, Breaker
from .displacement import displacement_direction


def find_breakers(candles: List[Candle], order_blocks: List[OrderBlock]) -> List[Breaker]:
    out: List[Breaker] = []
    for ob in order_blocks:
        for i in range(ob.event_index + 1, len(candles)):
            c = candles[i]
            if ob.direction == "bull":
                # bullish OB fails -> bearish breaker
                if c.close < ob.low and displacement_direction(candles, i) == "bear":
                    out.append(_make(ob, "bear", i, candles))
                    break
            else:
                # bearish OB fails -> bullish breaker
                if c.close > ob.high and displacement_direction(candles, i) == "bull":
                    out.append(_make(ob, "bull", i, candles))
                    break
    out.sort(key=lambda b: b.break_index)
    return out


def _make(ob: OrderBlock, new_dir: str, break_index: int, candles) -> Breaker:
    b = Breaker(
        index=ob.index, ts=ob.ts, direction=new_dir,
        low=ob.low, high=ob.high, ob_index=ob.index, break_index=break_index,
    )
    # retest: price returns to the zone after the break
    for i in range(break_index + 1, len(candles)):
        c = candles[i]
        if new_dir == "bull" and c.low <= b.high:      # support retest from above
            b.retested, b.retested_index = True, i
            return b
        if new_dir == "bear" and c.high >= b.low:      # resistance retest from below
            b.retested, b.retested_index = True, i
            return b
    return b
