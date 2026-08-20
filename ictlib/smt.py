"""SMT (Smart Money Technique) divergence (concepts/16-smt-divergence).

A price-action divergence between two correlated assets: one makes a new extreme
while the correlated asset fails to confirm. Needs a second, index-aligned candle
series (same timeframe). Common pairings: EURUSD/GBPUSD (positive), EURUSD/DXY
(negative), NQ/ES, gold/silver.
"""

from __future__ import annotations

from typing import List

from .models import Candle, SMTDivergence
from .concepts.structure import find_swings


def find_smt_divergence(
    candles_a: List[Candle],
    candles_b: List[Candle],
    *,
    correlation: str = "positive",
    width: int = 2,
) -> List[SMTDivergence]:
    """Detect SMT divergences on ``candles_a`` confirmed (or not) by ``candles_b``.

    The two series must be index-aligned (same timeframe, same bars).
    """
    n = min(len(candles_a), len(candles_b))
    swings = [s for s in find_swings(candles_a[:n], width)]
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    out: List[SMTDivergence] = []

    for pivots, kind in ((highs, "bear"), (lows, "bull")):
        for a, b in zip(pivots, pivots[1:]):
            i1, i2 = a.index, b.index
            if i2 >= n:
                continue
            if kind == "bear":
                a_new = candles_a[i2].high > candles_a[i1].high        # A new high
                if correlation == "positive":
                    b_fail = candles_b[i2].high < candles_b[i1].high    # B lower high
                else:
                    b_fail = candles_b[i2].low > candles_b[i1].low      # B fails new low
                lvl_a, lvl_b = candles_a[i2].high, candles_b[i2].high
            else:
                a_new = candles_a[i2].low < candles_a[i1].low           # A new low
                if correlation == "positive":
                    b_fail = candles_b[i2].low > candles_b[i1].low      # B higher low
                else:
                    b_fail = candles_b[i2].high < candles_b[i1].high    # B fails new high
                lvl_a, lvl_b = candles_a[i2].low, candles_b[i2].low
            if a_new and b_fail:
                out.append(SMTDivergence(i2, candles_a[i2].ts, kind,
                                         correlation, lvl_a, lvl_b))
    out.sort(key=lambda s: s.index)
    return out
