"""Asian range (concepts/14-asian-range/asian-range).

The range built during the Asia session — the engineered liquidity London
delivers from. Canonical KZ-anchored window is 20:00-00:00 NY; the full-session
anchor is 18:00-03:00. London/NY typically sweeps one bound (the Judas swing)
then expands toward multiples of the range size (asian-range-projections).
"""

from __future__ import annotations

from typing import List, Optional

from ..models import Candle, AsianRange
from .killzones import ny_minutes
from .sessions import _in, _instance_key, _m

_ANCHORS = {
    "kz": (_m(20), _m(24)),          # 20:00 -> 00:00 NY (inside the Asia KZ)
    "full": (_m(18), _m(3) + 1440),  # 18:00 -> 03:00 NY (full session)
}


def asian_range(candles: List[Candle], anchor: str = "kz") -> Optional[AsianRange]:
    if anchor not in _ANCHORS:
        raise ValueError("anchor must be 'kz' or 'full'")
    start, end = _ANCHORS[anchor]

    members = [(i, _instance_key(candles[i].ts, start))
               for i in range(len(candles))
               if _in(ny_minutes(candles[i].ts), start, end)]
    if not members:
        return None

    last_key = members[-1][1]
    idxs = [i for i, k in members if k == last_key]
    hi = max(idxs, key=lambda i: candles[i].high)
    lo = min(idxs, key=lambda i: candles[i].low)
    ar = AsianRange(
        high=candles[hi].high, low=candles[lo].low,
        high_index=hi, low_index=lo, start_index=idxs[0], end_index=idxs[-1],
    )

    # Judas swing: which bound gets swept first after the range closes?
    for i in range(ar.end_index + 1, len(candles)):
        c = candles[i]
        if c.high > ar.high:
            ar.swept_side = "high"
            break
        if c.low < ar.low:
            ar.swept_side = "low"
            break
    return ar
