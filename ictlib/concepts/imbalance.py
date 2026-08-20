"""Volume imbalance (concepts/06-fair-value-gaps/volume-imbalance).

A body-vs-body gap between two consecutive candles — the open of candle n gaps
away from the close of candle n-1. Wicks may overlap, so this is a softer,
FVG-like reference rather than a strict 3-candle FVG.

    bullish VI: O_n > C_{n-1}  → zone [C_{n-1}, O_n]
    bearish VI: O_n < C_{n-1}  → zone [O_n, C_{n-1}]
"""

from __future__ import annotations

from typing import List

from ..models import Candle, VolumeImbalance


def find_volume_imbalances(
    candles: List[Candle],
    *,
    min_size: float = 0.0,
) -> List[VolumeImbalance]:
    out: List[VolumeImbalance] = []
    for n in range(1, len(candles)):
        prev, cur = candles[n - 1], candles[n]
        if cur.open > prev.close:
            direction, low, high = "bull", prev.close, cur.open
        elif cur.open < prev.close:
            direction, low, high = "bear", cur.open, prev.close
        else:
            continue
        if high - low < min_size:
            continue
        vi = VolumeImbalance(n, cur.ts, direction, low, high)
        _mark(vi, candles)
        out.append(vi)
    return out


def _mark(vi: VolumeImbalance, candles: List[Candle]) -> None:
    for i in range(vi.index + 1, len(candles)):
        c = candles[i]
        if vi.direction == "bull" and c.low <= vi.high:
            vi.mitigated, vi.mitigated_index = True, i
            return
        if vi.direction == "bear" and c.high >= vi.low:
            vi.mitigated, vi.mitigated_index = True, i
            return
