"""Opening gaps — NDOG and NWOG (concepts/31-models/ndog, nwog).

NDOG (New Day Opening Gap): the gap between the prior day's NY-close and the
00:00 NY True Day Open. NWOG (New Week Opening Gap): the weekend gap between
Friday's close and the new-week open. Both are structural reference zones that
price tends to fill.
"""

from __future__ import annotations

from typing import List, Optional

from ..models import Candle, OpeningGap
from .quarterly import true_day_open


def _gap(candles, ref_i, open_i, kind) -> OpeningGap:
    prior_close = candles[ref_i].close
    new_open = candles[open_i].open
    lo, hi = sorted((prior_close, new_open))
    direction = "bull" if new_open > prior_close else "bear"
    return OpeningGap(kind, lo, hi, direction, ref_i, open_i)


def find_ndog(candles: List[Candle]) -> Optional[OpeningGap]:
    """The most recent New Day Opening Gap (prior close -> True Day Open)."""
    _, idx = true_day_open(candles)
    if idx is None or idx == 0:
        return None
    return _gap(candles, idx - 1, idx, "NDOG")


def find_nwog(candles: List[Candle], *, min_gap_hours: float = 36.0) -> Optional[OpeningGap]:
    """The most recent New Week Opening Gap (weekend gap in the series)."""
    best = None
    for i in range(1, len(candles)):
        dt = (candles[i].ts - candles[i - 1].ts).total_seconds() / 3600.0
        if dt >= min_gap_hours:
            best = i
    if best is None:
        return None
    return _gap(candles, best - 1, best, "NWOG")
