"""Order Block detection (concepts/07-order-blocks/order-block-criteria).

An OB is the last opposite-colour candle before a displacement move that breaks
structure. We derive OBs from the structure events already detected: for each
break we walk back through the displacement leg to the last opposite candle.

    bullish OB = last DOWN candle before bullish displacement + BOS/CHoCH
    bearish OB = last UP   candle before bearish displacement + BOS/CHoCH
    body zone  = [min(open,close), max(open,close)]     MT = body midpoint
    fresh      = not yet mitigated (price has not returned into the body)
"""

from __future__ import annotations

from typing import List

from ..models import Candle, OrderBlock, StructureEvent


def find_order_blocks(
    candles: List[Candle],
    events: List[StructureEvent],
    *,
    max_leg: int = 10,
) -> List[OrderBlock]:
    out: List[OrderBlock] = []
    seen: set[int] = set()
    for ev in events:
        ob_index = _last_opposite(candles, ev, max_leg)
        if ob_index is None or ob_index in seen:
            continue
        seen.add(ob_index)
        c = candles[ob_index]
        ob = OrderBlock(
            index=ob_index,
            ts=c.ts,
            direction=ev.direction,
            low=c.body_low,
            high=c.body_high,
            event_index=ev.index,
        )
        _mark_mitigation(ob, candles)
        out.append(ob)
    out.sort(key=lambda o: o.index)
    return out


def _last_opposite(candles, ev: StructureEvent, max_leg: int):
    """Walk left from the break candle across the displacement leg to the last
    candle of opposite colour to the break direction."""
    stop = max(0, ev.index - max_leg)
    if ev.direction == "bull":
        for j in range(ev.index, stop - 1, -1):
            if candles[j].is_bear:
                return j
    else:
        for j in range(ev.index, stop - 1, -1):
            if candles[j].is_bull:
                return j
    return None


def _mark_mitigation(ob: OrderBlock, candles: List[Candle]) -> None:
    for i in range(ob.event_index + 1, len(candles)):
        c = candles[i]
        if ob.direction == "bull" and c.low <= ob.high:
            ob.mitigated, ob.mitigated_index = True, i
            return
        if ob.direction == "bear" and c.high >= ob.low:
            ob.mitigated, ob.mitigated_index = True, i
            return


def unmitigated(obs: List[OrderBlock]) -> List[OrderBlock]:
    return [o for o in obs if not o.mitigated]
