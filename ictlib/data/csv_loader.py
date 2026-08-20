"""CSV OHLCV loader (stdlib only).

Accepts flexible headers. Recognised column aliases:
    time / timestamp / date / datetime
    open / o
    high / h
    low  / l
    close / c
    volume / vol / v   (optional)

Timestamps may be ISO-8601 (with or without timezone; naive is treated as UTC)
or a UNIX epoch (seconds). Rows are returned sorted by time.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from typing import List

from ..models import Candle

_ALIASES = {
    "time": {"time", "timestamp", "date", "datetime"},
    "open": {"open", "o"},
    "high": {"high", "h"},
    "low": {"low", "l"},
    "close": {"close", "c"},
    "volume": {"volume", "vol", "v"},
}


def _resolve(header: List[str]) -> dict:
    lower = {h.lower().strip(): h for h in header}
    cols = {}
    for key, names in _ALIASES.items():
        for n in names:
            if n in lower:
                cols[key] = lower[n]
                break
    missing = {"time", "open", "high", "low", "close"} - cols.keys()
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    return cols


def _parse_time(value: str) -> datetime:
    value = value.strip()
    # epoch seconds?
    try:
        if value.isdigit() or (value.replace(".", "", 1).isdigit()):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (ValueError, OverflowError):
        pass
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def load_csv(path: str) -> List[Candle]:
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        cols = _resolve(reader.fieldnames or [])
        out: List[Candle] = []
        for row in reader:
            out.append(Candle(
                ts=_parse_time(row[cols["time"]]),
                open=float(row[cols["open"]]),
                high=float(row[cols["high"]]),
                low=float(row[cols["low"]]),
                close=float(row[cols["close"]]),
                volume=float(row[cols["volume"]]) if "volume" in cols and row.get(cols["volume"]) else 0.0,
            ))
    out.sort(key=lambda c: c.ts)
    return out


def save_csv(path: str, candles: List[Candle]) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time", "open", "high", "low", "close", "volume"])
        for c in candles:
            w.writerow([c.ts.astimezone(timezone.utc).isoformat(),
                        c.open, c.high, c.low, c.close, c.volume])
