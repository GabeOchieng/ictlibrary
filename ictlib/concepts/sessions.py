"""Trading sessions and their ranges (concepts/15-sessions/session-overview).

ICT divides the day into NY-time sessions, each with a characteristic delivery
profile. Session extremes are resting liquidity. All windows are NY time and
DST-aware (via the killzone helpers).

    Session        Start   End     (NY)
    Asia           18:00   03:00   range-building (wraps midnight)
    London         02:00   11:00   often sets daily direction
    NY AM          08:00   12:00   NY-open displacement
    NY Lunch       12:00   13:30   consolidation
    NY PM          13:30   16:00   secondary delivery / reversals
    London Close   10:00   12:00   overlaps NY AM
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from ..models import Candle, SessionRange
from .killzones import ny_minutes, _NY


def _m(h: int, mi: int = 0) -> float:
    return h * 60 + mi


# (name, start_min, end_min) — end>1440 means it wraps past midnight
SESSION_WINDOWS = [
    ("Asia", _m(18), _m(3) + 1440),
    ("London", _m(2), _m(11)),
    ("NY AM", _m(8), _m(12)),
    ("NY Lunch", _m(12), _m(13, 30)),
    ("NY PM", _m(13, 30), _m(16)),
    ("London Close", _m(10), _m(12)),
]

# Non-overlapping partition used by session_of() (concepts/15-sessions formula)
_PARTITION = [
    ("Asia", _m(18), _m(3) + 1440),
    ("London", _m(2), _m(8)),
    ("NY AM", _m(8), _m(12)),
    ("NY Lunch", _m(12), _m(13, 30)),
    ("NY PM", _m(13, 30), _m(16)),
]


def _in(mins: float, start: float, end: float) -> bool:
    if end > 1440:
        return mins >= start or mins < (end - 1440)
    return start <= mins < end


def session_of(ts: datetime) -> Optional[str]:
    """Primary session for a timestamp (clean partition), or None if outside."""
    mins = ny_minutes(ts)
    for name, start, end in _PARTITION:
        if _in(mins, start, end):
            return name
    return None


def _ny_date(ts: datetime):
    return (ts.astimezone(_NY) if _NY else ts).date()


def _instance_key(ts: datetime, start: float):
    """Group candles into one session occurrence. For a midnight-wrapping
    session, the after-midnight portion belongs to the previous NY date."""
    local = ts.astimezone(_NY) if _NY else ts
    mins = local.hour * 60 + local.minute
    d = local.date()
    if start >= 1440 or (start >= _m(18) and mins < start and mins < 360):
        # after-midnight tail of a wrapping session -> previous day's instance
        d = d - timedelta(days=1)
    return d


def session_range(candles: List[Candle], name: str) -> Optional[SessionRange]:
    """High/low of the most recent occurrence of ``name`` present in ``candles``."""
    win = next((w for w in SESSION_WINDOWS if w[0] == name), None)
    if win is None:
        raise ValueError(f"unknown session {name!r}")
    _, start, end = win

    members = [(i, _instance_key(candles[i].ts, start))
               for i in range(len(candles))
               if _in(ny_minutes(candles[i].ts), start, end)]
    if not members:
        return None

    last_key = members[-1][1]
    idxs = [i for i, k in members if k == last_key]
    hi = max(idxs, key=lambda i: candles[i].high)
    lo = min(idxs, key=lambda i: candles[i].low)
    return SessionRange(
        name=name, high=candles[hi].high, low=candles[lo].low,
        high_index=hi, low_index=lo, start_index=idxs[0], end_index=idxs[-1],
    )


def pre_open_range(candles: List[Candle]) -> Optional[SessionRange]:
    """The 08:00-09:30 NY US-equity pre-cash-open range (used by the Venom model,
    concepts/31-models/venom-model)."""
    start, end = _m(8), _m(9, 30)
    members = [(i, _instance_key(candles[i].ts, start))
               for i in range(len(candles))
               if _in(ny_minutes(candles[i].ts), start, end)]
    if not members:
        return None
    last_key = members[-1][1]
    idxs = [i for i, k in members if k == last_key]
    hi = max(idxs, key=lambda i: candles[i].high)
    lo = min(idxs, key=lambda i: candles[i].low)
    return SessionRange("Pre-Open", candles[hi].high, candles[lo].low,
                        hi, lo, idxs[0], idxs[-1])


def all_session_ranges(candles: List[Candle]) -> List[SessionRange]:
    out = []
    for name, _, _ in SESSION_WINDOWS:
        sr = session_range(candles, name)
        if sr is not None:
            out.append(sr)
    return out
