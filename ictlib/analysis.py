"""Analysis orchestrator.

``analyze()`` runs every concept detector over a candle series and returns a
single ``Analysis`` snapshot. This is the foundation object that the scanner,
a backtester, or a live bot all consume — they never re-run the primitives
themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .models import (
    Candle, Swing, StructureEvent, FVG, OrderBlock, LiquidityPool, Sweep,
)
from .concepts import (
    find_swings, find_structure_events, current_bias, dealing_range,
    find_fvgs, find_order_blocks, find_pools, find_sweeps, infer_pip_size,
    active_killzone,
)


@dataclass
class Analysis:
    candles: List[Candle]
    pip: float
    swings: List[Swing] = field(default_factory=list)
    events: List[StructureEvent] = field(default_factory=list)
    fvgs: List[FVG] = field(default_factory=list)
    order_blocks: List[OrderBlock] = field(default_factory=list)
    pools: List[LiquidityPool] = field(default_factory=list)
    sweeps: List[Sweep] = field(default_factory=list)
    bias: str = "neutral"
    killzone: Optional[str] = None

    # -- convenience accessors -------------------------------------------- #
    @property
    def unmitigated_fvgs(self) -> List[FVG]:
        return [f for f in self.fvgs if not f.mitigated]

    @property
    def unmitigated_obs(self) -> List[OrderBlock]:
        return [o for o in self.order_blocks if not o.mitigated]

    @property
    def open_pools(self) -> List[LiquidityPool]:
        return [p for p in self.pools if not p.swept]

    def summary(self) -> dict:
        return {
            "candles": len(self.candles),
            "bias": self.bias,
            "killzone": self.killzone,
            "swings": len(self.swings),
            "structure_events": len(self.events),
            "fvgs": len(self.fvgs),
            "unmitigated_fvgs": len(self.unmitigated_fvgs),
            "order_blocks": len(self.order_blocks),
            "unmitigated_obs": len(self.unmitigated_obs),
            "liquidity_pools": len(self.pools),
            "sweeps": len(self.sweeps),
        }


def analyze(
    candles: List[Candle],
    *,
    swing_width: int = 2,
    pip: Optional[float] = None,
    eq_tolerance_pips: float = 5.0,
) -> Analysis:
    """Run the full primitive stack over ``candles``."""
    if pip is None:
        pip = infer_pip_size(candles)

    swings = find_swings(candles, width=swing_width)
    events = find_structure_events(candles, swings, width=swing_width)
    fvgs = find_fvgs(candles, require_displacement=True)
    obs = find_order_blocks(candles, events)
    pools = find_pools(swings, pip=pip, eq_tolerance_pips=eq_tolerance_pips)
    sweeps = find_sweeps(candles, pools)

    return Analysis(
        candles=candles,
        pip=pip,
        swings=swings,
        events=events,
        fvgs=fvgs,
        order_blocks=obs,
        pools=pools,
        sweeps=sweeps,
        bias=current_bias(events),
        killzone=active_killzone(candles[-1].ts) if candles else None,
    )
