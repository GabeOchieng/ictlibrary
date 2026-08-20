"""IPDA lookback levels (concepts/23-ipda).

The Interbank Price Delivery Algorithm references 20/40/60 trading-day lookback
windows to identify untaken reference highs/lows that price is drawn toward.
Computed by grouping candles into NY calendar days and taking the extreme over
the last N days. Degrades gracefully when fewer than N days are present.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import List

from ..models import Candle, IPDALevels
from .sessions import _ny_date


def ipda_levels(candles: List[Candle], lookbacks=(20, 40, 60)) -> IPDALevels:
    days: "OrderedDict[object, list]" = OrderedDict()
    for c in candles:
        d = _ny_date(c.ts)
        if d not in days:
            days[d] = [c.high, c.low]
        else:
            days[d][0] = max(days[d][0], c.high)
            days[d][1] = min(days[d][1], c.low)

    dates = list(days.keys())  # chronological (candles are time-sorted)
    levels = {}
    for n in lookbacks:
        recent = dates[-n:]
        if not recent:
            continue
        levels[f"{n}_high"] = max(days[d][0] for d in recent)
        levels[f"{n}_low"] = min(days[d][1] for d in recent)

    return IPDALevels(levels=levels, days_used=len(dates), lookbacks=tuple(lookbacks))
