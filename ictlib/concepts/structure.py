"""Market structure: swings and structural breaks
(concepts/01-market-structure).

Swing (3-bar / n-bar fractal):
    swing_high(n) := H_n > H_{n-1..n-w} AND H_n > H_{n+1..n+w}
    swing_low(n)  := L_n < L_{n-1..n-w} AND L_n < L_{n+1..n+w}
Confirmed only after ``w`` candles have closed to the right.

Structural break (close-based, referenced to the last opposite swing):
    bullish break := close > last confirmed swing high
    bearish break := close < last confirmed swing low
    BOS   = break in the direction of the prevailing trend (continuation)
    CHoCH = first break against the prevailing trend (reversal)
    MSS   = a CHoCH whose break candle shows displacement AND leaves an FVG
            (concepts/01-market-structure/mss)
"""

from __future__ import annotations

from typing import List, Optional

from ..models import Candle, Swing, StructureEvent
from .displacement import displacement_direction
from .fvg import find_fvgs


# --------------------------------------------------------------------------- #
# Swings
# --------------------------------------------------------------------------- #
def find_swings(candles: List[Candle], width: int = 2) -> List[Swing]:
    """Return confirmed fractal swing highs and lows, in index order."""
    swings: List[Swing] = []
    n = len(candles)
    for i in range(width, n - width):
        c = candles[i]
        left = candles[i - width:i]
        right = candles[i + 1:i + 1 + width]

        if all(c.high > o.high for o in left) and all(c.high > o.high for o in right):
            swings.append(Swing(i, c.ts, c.high, "high", width))
        # a candle can (rarely) be neither; it is never both with strict tests
        if all(c.low < o.low for o in left) and all(c.low < o.low for o in right):
            swings.append(Swing(i, c.ts, c.low, "low", width))
    swings.sort(key=lambda s: (s.index, 0 if s.kind == "high" else 1))
    return swings


def dealing_range(swings: List[Swing]) -> tuple[Optional[Swing], Optional[Swing]]:
    """Most recent confirmed swing high and swing low (the current range bounds)."""
    last_high = next((s for s in reversed(swings) if s.kind == "high"), None)
    last_low = next((s for s in reversed(swings) if s.kind == "low"), None)
    return last_high, last_low


# --------------------------------------------------------------------------- #
# Structural breaks
# --------------------------------------------------------------------------- #
def find_structure_events(
    candles: List[Candle],
    swings: Optional[List[Swing]] = None,
    *,
    width: int = 2,
) -> List[StructureEvent]:
    """Walk the candles and emit BOS / CHoCH / MSS events in time order."""
    if swings is None:
        swings = find_swings(candles, width)

    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    fvg_index = {f.index: f for f in find_fvgs(candles, require_displacement=True)}

    events: List[StructureEvent] = []
    trend: Optional[str] = None  # prevailing trend, set by the first break

    # pointers to the most recent *confirmed* swing available at candle i
    def last_before(pivots: List[Swing], i: int) -> Optional[Swing]:
        # a width-w swing at index p is confirmed once candle p+w has closed
        cand = [s for s in pivots if s.index + s.width < i]
        return cand[-1] if cand else None

    broken_high_idx = -1
    broken_low_idx = -1

    for i in range(len(candles)):
        c = candles[i]

        sh = last_before(highs, i)
        if sh and sh.index != broken_high_idx and c.close > sh.price:
            direction = "bull"
            kind = "BOS" if trend == "bull" else "CHoCH"
            ev = _make_event(candles, i, kind, direction, sh, fvg_index)
            if ev.kind == "CHoCH" and ev.has_displacement and ev.has_fvg:
                ev = StructureEvent(ev.index, ev.ts, "MSS", direction, ev.level,
                                    ev.swing_index, ev.has_fvg, ev.has_displacement)
            events.append(ev)
            trend = "bull"
            broken_high_idx = sh.index

        sl = last_before(lows, i)
        if sl and sl.index != broken_low_idx and c.close < sl.price:
            direction = "bear"
            kind = "BOS" if trend == "bear" else "CHoCH"
            ev = _make_event(candles, i, kind, direction, sl, fvg_index)
            if ev.kind == "CHoCH" and ev.has_displacement and ev.has_fvg:
                ev = StructureEvent(ev.index, ev.ts, "MSS", direction, ev.level,
                                    ev.swing_index, ev.has_fvg, ev.has_displacement)
            events.append(ev)
            trend = "bear"
            broken_low_idx = sl.index

    return events


def _make_event(candles, i, kind, direction, swing, fvg_index) -> StructureEvent:
    disp = displacement_direction(candles, i) == direction
    # FVG "in the break" — a same-direction FVG whose middle candle is the
    # break candle or one of its immediate neighbours.
    has_fvg = any(
        (j in fvg_index and fvg_index[j].direction == direction)
        for j in (i - 1, i, i + 1)
    )
    return StructureEvent(
        index=i, ts=candles[i].ts, kind=kind, direction=direction,
        level=swing.price, swing_index=swing.index,
        has_fvg=has_fvg, has_displacement=disp,
    )


def current_bias(events: List[StructureEvent]) -> str:
    """HTF/structural bias = direction of the most recent structural break."""
    if not events:
        return "neutral"
    return "bullish" if events[-1].direction == "bull" else "bearish"
