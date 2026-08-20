"""FVG-family variants (concepts/06-fair-value-gaps).

- Inversion FVG: an FVG traded through (close beyond the far edge with
  displacement) that flips polarity and acts as the opposite reference.
- Balanced Price Range: an overlapping bullish + bearish FVG — a two-sided
  decision zone.
- Nested FVG: an FVG fully contained inside a larger same-direction FVG.
"""

from __future__ import annotations

from typing import List, Tuple

from ..models import Candle, FVG, InversionFVG, BalancedPriceRange
from .displacement import displacement_direction


def find_inversion_fvgs(candles: List[Candle], fvgs: List[FVG]) -> List[InversionFVG]:
    out: List[InversionFVG] = []
    for f in fvgs:
        for i in range(f.index + 2, len(candles)):
            c = candles[i]
            if f.direction == "bull" and c.close < f.low and displacement_direction(candles, i) == "bear":
                out.append(InversionFVG(f.index, f.ts, "bear", f.low, f.high, i))
                break
            if f.direction == "bear" and c.close > f.high and displacement_direction(candles, i) == "bull":
                out.append(InversionFVG(f.index, f.ts, "bull", f.low, f.high, i))
                break
    return out


def find_bpr(fvgs: List[FVG]) -> List[BalancedPriceRange]:
    """Overlapping unmitigated bullish + bearish FVGs."""
    bulls = [f for f in fvgs if f.direction == "bull" and not f.mitigated]
    bears = [f for f in fvgs if f.direction == "bear" and not f.mitigated]
    out: List[BalancedPriceRange] = []
    for b in bulls:
        for s in bears:
            lo = max(b.low, s.low)
            hi = min(b.high, s.high)
            if lo < hi:
                out.append(BalancedPriceRange(lo, hi, b.index, s.index))
    return out


def find_nested_fvgs(fvgs: List[FVG]) -> List[Tuple[int, int]]:
    """Return (outer_index, inner_index) pairs where one FVG sits inside another
    of the same direction."""
    out: List[Tuple[int, int]] = []
    for a in fvgs:
        for b in fvgs:
            if a.index == b.index or a.direction != b.direction:
                continue
            if a.low <= b.low and b.high <= a.high and (a.high - a.low) > (b.high - b.low):
                out.append((a.index, b.index))
    return out
