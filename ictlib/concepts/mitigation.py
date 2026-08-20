"""Mitigation lifecycle (concepts/18-mitigation/partial-vs-full-mitigation).

A PD array moves through a 4-state lifecycle as price returns to it:

    fresh      — not touched since formation
    partial    — reached the near edge but not the midpoint (CE/MT)
    mitigated  — reached at least the midpoint (the default "tested" state)
    consumed   — reached at least the far edge
"""

from __future__ import annotations

from typing import List

from ..models import Candle


def mitigation_state(
    candles: List[Candle],
    from_index: int,
    low: float,
    high: float,
    direction: str,
) -> str:
    """Classify how deeply price has returned into a zone since ``from_index``.

    ``direction`` is the zone's protective side: "bull" = support (price returns
    from above), "bear" = resistance (price returns from below).
    """
    mid = (low + high) / 2.0
    if direction == "bull":
        near, far = high, low          # approaches downward: near edge = top
    else:
        near, far = low, high          # approaches upward: near edge = bottom

    deepest = None
    for i in range(from_index + 1, len(candles)):
        c = candles[i]
        reach = c.low if direction == "bull" else c.high
        deepest = reach if deepest is None else (min(deepest, reach)
                                                 if direction == "bull" else max(deepest, reach))
    if deepest is None:
        return "fresh"

    if direction == "bull":
        if deepest > near:
            return "fresh"
        if deepest <= far:
            return "consumed"
        return "mitigated" if deepest <= mid else "partial"
    else:
        if deepest < near:
            return "fresh"
        if deepest >= far:
            return "consumed"
        return "mitigated" if deepest >= mid else "partial"
