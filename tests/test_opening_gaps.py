"""Tests for NDOG / NWOG opening gaps."""

from datetime import datetime, timedelta, timezone

from ictlib.models import Candle
from ictlib.concepts.opening_gaps import find_ndog, find_nwog


def test_ndog_detects_day_open_gap():
    # prior day close 1.0800, then a gap up to the 00:00 NY True Day Open 1.0850.
    # 00:00 NY (EDT) = 04:00 UTC.
    d0 = datetime(2026, 8, 19, 3, 0, tzinfo=timezone.utc)   # prior day, 23:00 NY
    cs = [
        Candle(d0, 1.0805, 1.0810, 1.0795, 1.0800),                     # prior close
        Candle(d0 + timedelta(hours=1), 1.0850, 1.0860, 1.0845, 1.0855),  # 00:00 NY open
        Candle(d0 + timedelta(hours=2), 1.0855, 1.0865, 1.0850, 1.0860),
    ]
    ndog = find_ndog(cs)
    assert ndog is not None
    assert ndog.kind == "NDOG" and ndog.direction == "bull"
    assert ndog.low == 1.0800 and ndog.high == 1.0850


def test_nwog_detects_weekend_gap():
    fri = datetime(2026, 8, 21, 20, 0, tzinfo=timezone.utc)   # Friday close
    cs = [
        Candle(fri, 1.0900, 1.0905, 1.0895, 1.0900),
        # ~65h weekend gap -> Sunday/Monday open lower
        Candle(fri + timedelta(hours=65), 1.0850, 1.0855, 1.0845, 1.0850),
        Candle(fri + timedelta(hours=66), 1.0850, 1.0860, 1.0845, 1.0855),
    ]
    nwog = find_nwog(cs)
    assert nwog is not None
    assert nwog.kind == "NWOG" and nwog.direction == "bear"
    assert nwog.low == 1.0850 and nwog.high == 1.0900


def test_no_nwog_without_gap():
    base = datetime(2026, 8, 20, tzinfo=timezone.utc)
    cs = [Candle(base + timedelta(minutes=15 * i), 1.08, 1.081, 1.079, 1.0805)
          for i in range(10)]
    assert find_nwog(cs) is None
