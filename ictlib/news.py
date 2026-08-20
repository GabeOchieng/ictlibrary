"""News blackout windows (concepts/30-news-driven/news-blackout-rules).

ICT teaches a strict no-trade window around scheduled high-impact news. Given an
economic calendar (a list of NewsEvent), this flags whether a timestamp falls in
a blackout and enumerates the windows.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from .models import NewsEvent

# (pre-blackout, post-blackout) minutes by event kind (concepts/30 table)
BLACKOUT = {
    "fomc": (30, 60),
    "fomc_presser": (5, 60),
    "nfp": (15, 30),
    "cpi": (15, 30),
    "other": (5, 15),
}


def blackout_window(ev: NewsEvent) -> Tuple[datetime, datetime]:
    pre, post = BLACKOUT.get(ev.kind, BLACKOUT["other"])
    return ev.ts - timedelta(minutes=pre), ev.ts + timedelta(minutes=post)


def in_blackout(ts: datetime, events: List[NewsEvent]) -> Optional[NewsEvent]:
    """Return the event whose blackout window contains ``ts``, else None."""
    for ev in events:
        start, end = blackout_window(ev)
        if start <= ts <= end:
            return ev
    return None


def news_windows(events: List[NewsEvent]) -> List[Tuple[datetime, datetime, str]]:
    return [(*blackout_window(ev), ev.name) for ev in events]
