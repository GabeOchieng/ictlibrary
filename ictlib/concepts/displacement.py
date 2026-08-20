"""Displacement detection (concepts/09-displacement/displacement-definition).

Displacement is the *filter* that separates real OBs / FVGs / MSS events from
noise. A displacement candle:

    body   >= 1.5 * avg_body_recent
    body/range >= 0.70
    opposing_wick/range <= 0.20
    directional close (close in the top half for bull, bottom half for bear)
"""

from __future__ import annotations

from typing import List, Optional

from ..models import Candle


def avg_body(candles: List[Candle], index: int, lookback: int = 10) -> float:
    """Average body size of the ``lookback`` candles *before* ``index``."""
    start = max(0, index - lookback)
    window = candles[start:index]
    if not window:
        return 0.0
    return sum(c.body for c in window) / len(window)


def displacement_direction(
    candles: List[Candle],
    index: int,
    *,
    lookback: int = 10,
    body_mult: float = 1.5,
    body_ratio: float = 0.70,
    opp_wick_ratio: float = 0.20,
) -> Optional[str]:
    """Return "bull" / "bear" if candle ``index`` is displacement, else ``None``."""
    if index <= 0 or index >= len(candles):
        return None
    c = candles[index]
    if c.range <= 0:
        return None

    ab = avg_body(candles, index, lookback)
    # With no history to compare against, fall back to the shape-only tests.
    if ab > 0 and c.body < body_mult * ab:
        return None
    if c.body / c.range < body_ratio:
        return None

    if c.is_bull:
        opposing = c.upper_wick
        directional = c.close > c.midpoint
        direction = "bull"
    elif c.is_bear:
        opposing = c.lower_wick
        directional = c.close < c.midpoint
        direction = "bear"
    else:
        return None

    if opposing / c.range > opp_wick_ratio:
        return None
    if not directional:
        return None
    return direction


def is_displacement(candles: List[Candle], index: int, **kw) -> bool:
    return displacement_direction(candles, index, **kw) is not None
