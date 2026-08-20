"""Order-block variants (concepts/07-order-blocks).

- Propulsion block: the wide-body takeoff candle right after an OB that launches
  the displacement (a continuation reference, not the absorption candle).
- Reclaimed OB: a mitigated OB that price reclaimed and now respects again.
"""

from __future__ import annotations

from typing import List

from ..models import Candle, OrderBlock, PropulsionBlock
from .displacement import avg_body


def find_propulsion_blocks(
    candles: List[Candle],
    order_blocks: List[OrderBlock],
    *,
    body_mult: float = 1.5,
    opp_wick_ratio: float = 0.20,
) -> List[PropulsionBlock]:
    out: List[PropulsionBlock] = []
    seen: set[int] = set()
    for ob in order_blocks:
        j = ob.index + 1                       # takeoff candle after the OB
        if j >= len(candles) or j in seen:
            continue
        c = candles[j]
        if c.range <= 0:
            continue
        aligned = (c.is_bull and ob.direction == "bull") or (c.is_bear and ob.direction == "bear")
        wide = c.body >= body_mult * (avg_body(candles, j) or c.body)
        opp = (c.upper_wick if c.is_bull else c.lower_wick) / c.range
        if aligned and wide and opp <= opp_wick_ratio:
            seen.add(j)
            out.append(PropulsionBlock(j, c.ts, ob.direction, c.body_low, c.body_high))
    return out


def find_reclaimed_obs(candles: List[Candle], order_blocks: List[OrderBlock]) -> List[OrderBlock]:
    """Mitigated OBs that price returned to a SECOND time and respected again
    (concepts/07-order-blocks/reclaimed-order-block) — an old block reused."""
    out: List[OrderBlock] = []
    for ob in order_blocks:
        if not ob.mitigated or ob.mitigated_index is None:
            continue
        # a later re-touch of the body after the first mitigation
        for i in range(ob.mitigated_index + 1, len(candles)):
            c = candles[i]
            touched = (ob.direction == "bull" and c.low <= ob.high) or \
                      (ob.direction == "bear" and c.high >= ob.low)
            if touched:
                out.append(ob)
                break
    return out

