"""Liquidity pools and sweeps (concepts/02-liquidity).

Pools:
    BSL (buy-side)  = resting buy stops above price, at swing highs / equal highs
    SSL (sell-side) = resting sell stops below price, at swing lows / equal lows
    EQH/EQL         = clusters of swing highs/lows within a pip tolerance
                      (the densest liquidity pools)

Sweep (liquidity-sweep):
    BSL sweep := high>level AND close<level AND (high-close) > 0.6*range
    SSL sweep := low<level  AND close>level AND (close-low) > 0.6*range
The decisive feature is the close direction: opposite the wick. A close beyond
the level is a break of structure, not a sweep.
"""

from __future__ import annotations

from typing import List

from ..models import Candle, Swing, LiquidityPool, Sweep


def find_pools(
    swings: List[Swing],
    *,
    pip: float,
    eq_tolerance_pips: float = 5.0,
) -> List[LiquidityPool]:
    """Build liquidity pools from swings, clustering equal highs/lows."""
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    tol = eq_tolerance_pips * pip

    pools: List[LiquidityPool] = []
    pools += _cluster(highs, "BSL", "EQH", tol)
    pools += _cluster(lows, "SSL", "EQL", tol)
    pools.sort(key=lambda p: p.index)
    return pools


def _cluster(pivots: List[Swing], kind: str, eq_label: str, tol: float):
    out: List[LiquidityPool] = []
    used = [False] * len(pivots)
    for i, s in enumerate(pivots):
        if used[i]:
            continue
        members = [i]
        for j in range(i + 1, len(pivots)):
            if not used[j] and abs(pivots[j].price - s.price) <= tol:
                members.append(j)
                used[j] = True
        used[i] = True
        anchor = pivots[members[-1]]  # most recent pivot in the cluster
        label = eq_label if len(members) > 1 else "swing"
        price = sum(pivots[m].price for m in members) / len(members)
        out.append(LiquidityPool(
            kind=kind, price=price, index=anchor.index, label=label,
            members=[pivots[m].index for m in members],
        ))
    return out


def find_sweeps(
    candles: List[Candle],
    pools: List[LiquidityPool],
    *,
    wick_ratio: float = 0.6,
) -> List[Sweep]:
    """Detect the first candle that sweeps each pool (and mark the pool swept)."""
    sweeps: List[Sweep] = []
    for pool in pools:
        for i in range(pool.index + 1, len(candles)):
            c = candles[i]
            if c.range <= 0:
                continue
            if pool.kind == "BSL":
                if c.high > pool.price and c.close < pool.price:
                    wick = (c.high - c.close) / c.range
                    if wick >= wick_ratio:
                        sweeps.append(Sweep(i, c.ts, "BSL", pool.price,
                                            c.high, c.close, wick, pool.index))
                        pool.swept, pool.swept_index = True, i
                        break
            else:  # SSL
                if c.low < pool.price and c.close > pool.price:
                    wick = (c.close - c.low) / c.range
                    if wick >= wick_ratio:
                        sweeps.append(Sweep(i, c.ts, "SSL", pool.price,
                                            c.low, c.close, wick, pool.index))
                        pool.swept, pool.swept_index = True, i
                        break
    sweeps.sort(key=lambda s: s.index)
    return sweeps


def find_liquidity_voids(
    candles: List[Candle],
    *,
    span: int = 4,
    directional_pct: float = 0.8,
    max_pullback: float = 0.3,
) -> List["LiquidityVoid"]:
    """Wide one-sided expansion spans (concepts/02/liquidity-void): >=80% of
    closes in one direction and pullbacks small relative to the move."""
    from ..models import LiquidityVoid
    out: List[LiquidityVoid] = []
    i = 0
    n = len(candles)
    while i < n - span:
        window = candles[i:i + span]
        ups = sum(1 for c in window if c.is_bull)
        downs = span - ups
        hi = max(c.high for c in window)
        lo = min(c.low for c in window)
        size = hi - lo
        if size <= 0:
            i += 1
            continue
        if ups / span >= directional_pct:
            direction = "bull"
        elif downs / span >= directional_pct:
            direction = "bear"
        else:
            i += 1
            continue
        # pullback = largest counter-move within the span
        pull = _max_pullback(window, direction)
        if pull <= max_pullback * size:
            out.append(LiquidityVoid(i, i + span - 1, direction, lo, hi))
            i += span
        else:
            i += 1
    return out


def _max_pullback(window, direction) -> float:
    worst = 0.0
    if direction == "bull":
        peak = window[0].high
        for c in window:
            peak = max(peak, c.high)
            worst = max(worst, peak - c.low)
    else:
        trough = window[0].low
        for c in window:
            trough = min(trough, c.low)
            worst = max(worst, c.high - trough)
    return worst


def infer_pip_size(candles: List[Candle]) -> float:
    """Guess the pip size from price magnitude (JPY pairs ~0.01, others 0.0001)."""
    if not candles:
        return 0.0001
    price = candles[-1].close
    return 0.01 if price >= 20 else 0.0001
