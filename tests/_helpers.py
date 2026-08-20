"""Shared test helpers."""

from datetime import datetime, timedelta, timezone

from ictlib.models import Candle

BASE = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def candles(rows, minutes=15, base=BASE):
    """Build candles from (open, high, low, close[, volume]) tuples."""
    out = []
    for i, r in enumerate(rows):
        o, h, l, c = r[0], r[1], r[2], r[3]
        v = r[4] if len(r) > 4 else 1000
        out.append(Candle(base + timedelta(minutes=minutes * i), o, h, l, c, v))
    return out
