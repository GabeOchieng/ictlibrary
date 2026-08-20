"""Fair Value Gap detection (concepts/06-fair-value-gaps/fair-value-gap).

bullish FVG (BISI):  L[n+1] > H[n-1]   region = [H[n-1], L[n+1]]
bearish FVG (SIBI):  H[n+1] < L[n-1]   region = [H[n+1], L[n-1]]

Wicks are used, not bodies. Candle n must show displacement (criterion c3).
The gap persists until rebalanced (price trades back into the region).
"""

from __future__ import annotations

from typing import List

from ..models import Candle, FVG
from .displacement import displacement_direction


def find_fvgs(
    candles: List[Candle],
    *,
    require_displacement: bool = True,
    min_size: float = 0.0,
) -> List[FVG]:
    """Detect every FVG in ``candles`` and mark whether each is mitigated."""
    out: List[FVG] = []
    for n in range(1, len(candles) - 1):
        prev, mid, nxt = candles[n - 1], candles[n], candles[n + 1]
        disp = displacement_direction(candles, n)

        if nxt.low > prev.high:  # bullish gap
            direction = "bull"
            low, high = prev.high, nxt.low
        elif nxt.high < prev.low:  # bearish gap
            direction = "bear"
            low, high = nxt.high, prev.low
        else:
            continue

        has_disp = disp == direction
        if require_displacement and not has_disp:
            continue
        if high - low < min_size:
            continue

        fvg = FVG(
            index=n,
            ts=mid.ts,
            direction=direction,
            low=low,
            high=high,
            has_displacement=has_disp,
        )
        _mark_mitigation(fvg, candles)
        out.append(fvg)
    return out


def _mark_mitigation(fvg: FVG, candles: List[Candle]) -> None:
    """A gap is mitigated once a later candle trades back into the region."""
    for i in range(fvg.index + 2, len(candles)):
        c = candles[i]
        if fvg.direction == "bull" and c.low <= fvg.high:
            fvg.mitigated, fvg.mitigated_index = True, i
            return
        if fvg.direction == "bear" and c.high >= fvg.low:
            fvg.mitigated, fvg.mitigated_index = True, i
            return


def unmitigated(fvgs: List[FVG]) -> List[FVG]:
    return [f for f in fvgs if not f.mitigated]
