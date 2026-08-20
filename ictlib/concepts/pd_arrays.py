"""PD arrays: dealing range, equilibrium, premium/discount
(concepts/05-pd-arrays, concepts/27-equilibrium).

The dealing range is bounded by the most recent unbroken long-term high (LTH)
and long-term low (LTL). Those come from the ICT fractal hierarchy on the swings
(concepts/01-market-structure/swing-high):

    STH  = any 3-bar swing high
    ITH  = an STH whose adjacent STHs are both lower
    LTH  = an ITH whose adjacent ITHs are both lower   (symmetric for lows)

Once the range is known, every price / PD array is classified relative to
equilibrium EQ = (LTH + LTL) / 2:  above = premium (sell-side reference),
below = discount (buy-side reference). ICT discipline: longs originate at a
discount, shorts at a premium.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..models import Candle, Swing, DealingRange

_HIGH_DEGREE = {1: "STH", 2: "ITH", 3: "LTH"}
_LOW_DEGREE = {1: "STL", 2: "ITL", 3: "LTL"}


def swing_degrees(swings: List[Swing], kind: str) -> Tuple[List[Swing], List[int]]:
    """Return (pivots_of_kind, degree) where degree is 1=ST, 2=IT, 3=LT.

    A pivot is promoted a degree when both its same-degree neighbours are less
    extreme than it (higher-degree confirmation needs a neighbour on each side).
    """
    pts = [s for s in swings if s.kind == kind]
    prices = [s.price for s in pts]
    n = len(prices)
    deg = [1] * n
    for target in (2, 3):
        idxs = [i for i in range(n) if deg[i] == target - 1]
        for k in range(1, len(idxs) - 1):
            i, prev, nxt = idxs[k], idxs[k - 1], idxs[k + 1]
            more_extreme = (
                prices[i] > prices[prev] and prices[i] > prices[nxt]
                if kind == "high"
                else prices[i] < prices[prev] and prices[i] < prices[nxt]
            )
            if more_extreme:
                deg[i] = target
    return pts, deg


def _pick_bound(pts: List[Swing], deg: List[int]) -> Tuple[int, float, int]:
    """Most recent pivot of the highest degree present. Returns (index, price, degree)."""
    top_deg = max(deg)
    cands = [(pts[i].index, pts[i].price) for i in range(len(pts)) if deg[i] == top_deg]
    idx, price = max(cands)  # most recent (largest candle index)
    return idx, price, top_deg


def find_dealing_range(
    candles: List[Candle],
    swings: List[Swing],
) -> Optional[DealingRange]:
    """Build the current dealing range from the swing hierarchy."""
    if not candles:
        return None

    highs, hdeg = swing_degrees(swings, "high")
    lows, ldeg = swing_degrees(swings, "low")

    if not highs or not lows:
        # fallback: use the visible extremes as the reference range
        top = max(c.high for c in candles)
        bot = min(c.low for c in candles)
        ti = max(range(len(candles)), key=lambda i: candles[i].high)
        bi = min(range(len(candles)), key=lambda i: candles[i].low)
        return DealingRange(top, bot, ti, bi, "RANGE", "RANGE")

    ti, top, td = _pick_bound(highs, hdeg)
    bi, bot, bd = _pick_bound(lows, ldeg)

    if top <= bot:  # degenerate: widen to visible extremes
        top = max(c.high for c in candles)
        bot = min(c.low for c in candles)
        ti = max(range(len(candles)), key=lambda i: candles[i].high)
        bi = min(range(len(candles)), key=lambda i: candles[i].low)
        return DealingRange(top, bot, ti, bi, "RANGE", "RANGE")

    return DealingRange(top, bot, ti, bi, _HIGH_DEGREE[td], _LOW_DEGREE[bd])
