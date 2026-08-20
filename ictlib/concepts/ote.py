"""Optimal Trade Entry (concepts/17-optimal-trade-entry/ote-rules).

OTE is a retracement zone on a measured impulse leg. Fib is anchored to the
leg's terminal and origin pivots. The whole [0.62, 0.79] band is tradable; the
0.705 level is the classic midpoint. 0.79 is the *deepest entry*, not the stop.

For a bullish leg (origin = low, terminal = high) a retracement of fraction r
sits at:  price = high - r * (high - low).
"""

from __future__ import annotations

from typing import NamedTuple

OTE_LOW = 0.62
OTE_MID = 0.705
OTE_HIGH = 0.79


class OTE(NamedTuple):
    direction: str        # "bull" | "bear"
    leg_low: float
    leg_high: float
    entry_62: float
    entry_705: float
    entry_79: float

    @property
    def zone(self) -> tuple[float, float]:
        lo = min(self.entry_62, self.entry_79)
        hi = max(self.entry_62, self.entry_79)
        return lo, hi

    def contains(self, price: float) -> bool:
        lo, hi = self.zone
        return lo <= price <= hi


def _retrace(low: float, high: float, direction: str, r: float) -> float:
    if direction == "bull":
        return high - r * (high - low)
    return low + r * (high - low)


# Standard-deviation projection sets (concepts/28-fibonacci-levels/
# standard-deviation-projections). The OTE-series preset is the shallower one.
SD_OTE = (-0.5, -1.0, -1.5, -2.0)
SD_WIDE = (-1.5, -2.0, -2.5, -4.0)


def measured_leg(candles, start_i: int, end_i: int, direction: str,
                 anchor: str = "body") -> tuple:
    """The (leg_start, leg_end) for a measured leg (concepts/28/fib-anchoring).

    ICT anchors fibs to candle BODIES, not wicks — wicks differ most between
    brokers, so a wick-anchored measurement is not reproducible. PD arrays keep
    their own wick conventions; this governs the fib tool only.
    """
    seg = candles[start_i:end_i + 1] or [candles[start_i]]
    if anchor == "body":
        highs = [c.body_high for c in seg]
        lows = [c.body_low for c in seg]
    else:
        highs = [c.high for c in seg]
        lows = [c.low for c in seg]
    if direction == "bull":
        return min(lows), max(highs)
    return max(highs), min(lows)


def sd_projections(leg_start: float, leg_end: float, levels=SD_OTE) -> dict:
    """Extension targets beyond a measured leg: project(level) = leg_end -
    level*leg_size, with negative levels extending past leg_end."""
    leg_size = leg_end - leg_start
    return {f"{lvl}SD": leg_end - lvl * leg_size for lvl in levels}


def ote_from_leg(leg_start: float, leg_end: float, direction: str) -> OTE:
    """Build the OTE band from a measured leg's origin and terminal prices."""
    low, high = min(leg_start, leg_end), max(leg_start, leg_end)
    return OTE(
        direction=direction,
        leg_low=low,
        leg_high=high,
        entry_62=_retrace(low, high, direction, OTE_LOW),
        entry_705=_retrace(low, high, direction, OTE_MID),
        entry_79=_retrace(low, high, direction, OTE_HIGH),
    )
