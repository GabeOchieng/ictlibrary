"""Killzones and macro/silver-bullet windows
(concepts/10-killzones/killzone-times-table).

All windows are defined in New York clock time; DST is handled by the
America/New_York zoneinfo database. A candle's timestamp (UTC) is converted to
NY time and matched against the windows below.

    Killzone       Window (NY)
    Asia           20:00 – 00:00
    London Open    02:00 – 05:00   (silver bullet 03:00–04:00)
    NY AM          08:00 – 11:00   (silver bullet 10:00–11:00)
    London Close   10:00 – 12:00
    NY PM          13:30 – 16:00   (silver bullet 14:00–15:00)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, NamedTuple

try:
    from zoneinfo import ZoneInfo
    _NY = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - fallback if tzdata missing
    _NY = None


class Window(NamedTuple):
    name: str
    start: float   # minutes from NY midnight
    end: float
    kind: str      # "killzone" | "silver_bullet" | "macro"


def _m(h: int, mi: int = 0) -> float:
    return h * 60 + mi


KILLZONES: List[Window] = [
    Window("Asia", _m(20), _m(24), "killzone"),          # wraps midnight
    Window("London Open", _m(2), _m(5), "killzone"),
    Window("NY AM", _m(8), _m(11), "killzone"),
    Window("London Close", _m(10), _m(12), "killzone"),
    Window("NY PM", _m(13, 30), _m(16), "killzone"),
]

SILVER_BULLETS: List[Window] = [
    Window("Silver Bullet London", _m(3), _m(4), "silver_bullet"),
    Window("Silver Bullet NY AM", _m(10), _m(11), "silver_bullet"),
    Window("Silver Bullet NY PM", _m(14), _m(15), "silver_bullet"),
]

MACROS: List[Window] = [
    Window("Macro London Open", _m(2, 50), _m(3, 10), "macro"),
    Window("Macro NY Pre-Open", _m(9, 50), _m(10, 10), "macro"),
    Window("Macro NY First PM", _m(13, 50), _m(14, 10), "macro"),
    Window("Macro NY Mid-PM", _m(14, 50), _m(15, 10), "macro"),
]

ALL_WINDOWS = KILLZONES + SILVER_BULLETS + MACROS


def ny_minutes(ts: datetime) -> float:
    """Minutes past midnight in New York for a UTC timestamp."""
    local = ts.astimezone(_NY) if _NY else ts
    return local.hour * 60 + local.minute + local.second / 60.0


def _in(mins: float, w: Window) -> bool:
    if w.end > 24 * 60:  # wraps past midnight (Asia)
        return mins >= w.start or mins < (w.end - 24 * 60)
    return w.start <= mins < w.end


def active_windows(ts: datetime, windows: List[Window] = KILLZONES) -> List[Window]:
    mins = ny_minutes(ts)
    return [w for w in windows if _in(mins, w)]


def active_killzone(ts: datetime) -> str | None:
    """Return the name of the active killzone, or ``None`` if outside all."""
    act = active_windows(ts, KILLZONES)
    return act[0].name if act else None


def in_silver_bullet(ts: datetime) -> bool:
    return bool(active_windows(ts, SILVER_BULLETS))
