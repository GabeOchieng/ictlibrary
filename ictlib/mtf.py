"""Multi-timeframe HTF bias (concepts/25-htf-bias/top-down-analysis).

ICT reads bias top-down — monthly → weekly → daily → H4 → H1 — and only takes
setups aligned with it (longs on bullish, shorts on bearish, nothing on
neutral). Here we resample the entry-TF candles up to a set of higher
timeframes, read each one's structural bias and side of equilibrium, and
aggregate into a single directional bias with a conflict flag.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import List, Optional

from .models import Candle, TFRead, MTFContext
from .concepts import (
    find_swings, find_structure_events, current_bias, find_dealing_range,
)

# minutes -> label for common ICT timeframes
_TF_LABELS = [
    (1, "M1"), (5, "M5"), (15, "M15"), (30, "M30"),
    (60, "H1"), (240, "H4"), (1440, "D"), (10080, "W"), (43200, "MN"),
]


def tf_label(minutes: int) -> str:
    for m, lbl in _TF_LABELS:
        if minutes == m:
            return lbl
    return f"{minutes}m"


def infer_tf_minutes(candles: List[Candle]) -> int:
    """Estimate the entry timeframe from the median spacing between candles."""
    if len(candles) < 2:
        return 15
    deltas = [(candles[i].ts - candles[i - 1].ts).total_seconds() / 60.0
              for i in range(1, len(candles))]
    return max(int(round(median(deltas))), 1)


def resample_tf(candles: List[Candle], minutes: int) -> List[Candle]:
    """Aggregate candles into higher-timeframe bars aligned to UTC epoch buckets."""
    period = minutes * 60
    out: List[Candle] = []
    cur = None
    o = h = l = c = 0.0
    vol = 0.0
    ts0 = None
    for cd in candles:
        key = int(cd.ts.astimezone(timezone.utc).timestamp() // period)
        if cur is None or key != cur:
            if cur is not None:
                out.append(Candle(ts0, o, h, l, c, vol))
            cur = key
            o, h, l, c, vol = cd.open, cd.high, cd.low, cd.close, cd.volume
            ts0 = datetime.fromtimestamp(key * period, tz=timezone.utc)
        else:
            h, l, c = max(h, cd.high), min(l, cd.low), cd.close
            vol += cd.volume
    if cur is not None:
        out.append(Candle(ts0, o, h, l, c, vol))
    return out


def timeframe_read(candles: List[Candle], minutes: int) -> Optional[TFRead]:
    """Read one timeframe's structural bias + side of equilibrium."""
    if len(candles) < 5:
        return None
    swings = find_swings(candles)
    events = find_structure_events(candles, swings)
    dr = find_dealing_range(candles, swings)
    side = dr.classify(candles[-1].close) if dr else None
    return TFRead(label=tf_label(minutes), minutes=minutes,
                  bias=current_bias(events), eq_side=side, candles=len(candles))


def multi_timeframe_bias(
    candles: List[Candle],
    htf_minutes: List[int],
) -> MTFContext:
    """Resample to each higher timeframe and aggregate a top-down bias."""
    entry = infer_tf_minutes(candles)
    reads: List[TFRead] = []
    for m in sorted(set(htf_minutes), reverse=True):   # highest TF first
        if m <= entry:
            continue
        r = timeframe_read(resample_tf(candles, m), m)
        if r is not None:
            reads.append(r)

    votes = [r.bias for r in reads if r.bias in ("bullish", "bearish")]
    nb, ns = votes.count("bullish"), votes.count("bearish")
    if nb and not ns:
        agg = "bullish"
    elif ns and not nb:
        agg = "bearish"
    elif nb > ns:
        agg = "bullish"
    elif ns > nb:
        agg = "bearish"
    else:
        agg = "neutral"
    return MTFContext(reads=reads, bias=agg, conflict=(nb > 0 and ns > 0),
                      entry_minutes=entry)
