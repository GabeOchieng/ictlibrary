"""Turtle Soup — failed-breakout pattern (concepts/20-turtle-soup).

    bullish TS: low(n) < SSL, close(n+k) > SSL for k in [0,3], then up displacement
    bearish TS: high(n) > BSL, close(n+k) < BSL for k in [0,3], then down displacement

It is the named form of a liquidity sweep with a confirming reversal, so we
build it from the sweeps already detected plus a displacement check.
"""

from __future__ import annotations

from typing import List

from ..models import Candle, Sweep, TurtleSoup
from .displacement import displacement_direction


def find_turtle_soups(
    candles: List[Candle],
    sweeps: List[Sweep],
    *,
    confirm_within: int = 3,
) -> List[TurtleSoup]:
    out: List[TurtleSoup] = []
    for sw in sweeps:
        # SSL sweep -> bullish reversal; BSL sweep -> bearish reversal
        want = "bull" if sw.kind == "SSL" else "bear"
        end = min(sw.index + confirm_within, len(candles) - 1)
        for j in range(sw.index, end + 1):
            if displacement_direction(candles, j) == want:
                out.append(TurtleSoup(
                    index=sw.index, ts=sw.ts, direction=want,
                    level=sw.level, confirm_index=j,
                ))
                break
    return out
