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
    DealingRange, Breaker, RejectionBlock, VolumeImbalance,
    SessionRange, AsianRange, IPDALevels,
    TurtleSoup, CRTSetup, QuarterlyContext, MTFContext, Unicorn,
    InversionFVG, BalancedPriceRange, LiquidityVoid, PropulsionBlock,
    SMTDivergence, NewsEvent, OpeningGap,
)
from .concepts import (
    find_swings, find_structure_events, current_bias, dealing_range,
    find_fvgs, find_order_blocks, find_pools, find_sweeps, infer_pip_size,
    active_killzone, find_dealing_range,
    find_breakers, find_rejection_blocks, find_volume_imbalances,
    all_session_ranges, asian_range, ipda_levels,
    find_turtle_soups, quarterly_context, find_crt_setups,
    find_inversion_fvgs, find_bpr, find_nested_fvgs,
    find_propulsion_blocks, find_liquidity_voids,
    classify_internal_external, range_state,
    find_ndog, find_nwog, find_reclaimed_obs, classify_stop_runs,
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
    breakers: List[Breaker] = field(default_factory=list)
    rejection_blocks: List[RejectionBlock] = field(default_factory=list)
    volume_imbalances: List[VolumeImbalance] = field(default_factory=list)
    session_ranges: List[SessionRange] = field(default_factory=list)
    asian_range: Optional[AsianRange] = None
    ipda: Optional[IPDALevels] = None
    turtle_soups: List[TurtleSoup] = field(default_factory=list)
    crt_setups: List[CRTSetup] = field(default_factory=list)
    quarterly: Optional[QuarterlyContext] = None
    mtf: Optional[MTFContext] = None
    unicorns: List[Unicorn] = field(default_factory=list)
    diamonds: list = field(default_factory=list)
    inversion_fvgs: List[InversionFVG] = field(default_factory=list)
    bpr: List[BalancedPriceRange] = field(default_factory=list)
    nested_fvgs: list = field(default_factory=list)
    liquidity_voids: List[LiquidityVoid] = field(default_factory=list)
    propulsion_blocks: List[PropulsionBlock] = field(default_factory=list)
    range_state: str = "unknown"
    reclaimed_obs: List[OrderBlock] = field(default_factory=list)
    stop_runs: list = field(default_factory=list)
    smt_divergences: List[SMTDivergence] = field(default_factory=list)
    news_blackout: Optional[NewsEvent] = None
    ndog: Optional[OpeningGap] = None
    nwog: Optional[OpeningGap] = None
    dealing_range: Optional[DealingRange] = None
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

    def draw_on_liquidity(self, side: str) -> List[float]:
        """The IPDA reference set of draw-on-liquidity levels on one side:
        pool prices + session/Asian-range extremes + IPDA lookback levels.

        ``side`` "up" returns levels above (long targets / BSL), "down" below.
        """
        levels: List[float] = []
        want_high = side == "up"
        for p in self.pools:
            if (p.kind == "BSL") == want_high:
                levels.append(p.price)
        for sr in self.session_ranges:
            levels.append(sr.high if want_high else sr.low)
        if self.asian_range is not None:
            levels.append(self.asian_range.high if want_high else self.asian_range.low)
        if self.ipda is not None:
            key = "high" if want_high else "low"
            levels += [v for k, v in self.ipda.levels.items() if k.endswith(key)]
        return sorted(set(levels), reverse=not want_high)

    @property
    def price_state(self) -> Optional[str]:
        """Where the latest close sits relative to dealing-range equilibrium."""
        if not self.dealing_range or not self.candles:
            return None
        return self.dealing_range.classify(self.candles[-1].close)

    def summary(self) -> dict:
        dr = self.dealing_range
        return {
            "candles": len(self.candles),
            "bias": self.bias,
            "killzone": self.killzone,
            "price_state": self.price_state,
            "equilibrium": round(dr.eq, 5) if dr else None,
            "swings": len(self.swings),
            "structure_events": len(self.events),
            "fvgs": len(self.fvgs),
            "unmitigated_fvgs": len(self.unmitigated_fvgs),
            "order_blocks": len(self.order_blocks),
            "unmitigated_obs": len(self.unmitigated_obs),
            "liquidity_pools": len(self.pools),
            "sweeps": len(self.sweeps),
            "breakers": len(self.breakers),
            "rejection_blocks": len(self.rejection_blocks),
            "volume_imbalances": len(self.volume_imbalances),
            "session_ranges": len(self.session_ranges),
            "asian_range": bool(self.asian_range),
            "ipda_days": self.ipda.days_used if self.ipda else 0,
            "turtle_soups": len(self.turtle_soups),
            "crt_setups": len(self.crt_setups),
            "quarter": self.quarterly.daily_quarter if self.quarterly else None,
            "phase": self.quarterly.phase if self.quarterly else None,
            "htf_bias": self.mtf.bias if self.mtf else None,
            "htf_reads": [(r.label, r.bias) for r in self.mtf.reads] if self.mtf else [],
            "unicorns": len(self.unicorns),
            "diamonds": len(self.diamonds),
            "inversion_fvgs": len(self.inversion_fvgs),
            "bpr": len(self.bpr),
            "nested_fvgs": len(self.nested_fvgs),
            "liquidity_voids": len(self.liquidity_voids),
            "propulsion_blocks": len(self.propulsion_blocks),
            "range_state": self.range_state,
            "smt_divergences": len(self.smt_divergences),
            "news_blackout": self.news_blackout.name if self.news_blackout else None,
            "ndog": bool(self.ndog),
            "nwog": bool(self.nwog),
            "reclaimed_obs": len(self.reclaimed_obs),
            "stop_runs": len(self.stop_runs),
        }


def analyze(
    candles: List[Candle],
    *,
    swing_width: int = 2,
    pip: Optional[float] = None,
    eq_tolerance_pips: float = 5.0,
    htf_timeframes: Optional[List[int]] = None,
    smt_reference: Optional[List[Candle]] = None,
    smt_correlation: str = "positive",
    news_events: Optional[List[NewsEvent]] = None,
) -> Analysis:
    """Run the full primitive stack over ``candles``.

    ``htf_timeframes`` (minutes, e.g. ``[60, 240]``) enables the multi-timeframe
    top-down HTF bias read (concepts/25-htf-bias).
    """
    if pip is None:
        pip = infer_pip_size(candles)

    swings = find_swings(candles, width=swing_width)
    events = find_structure_events(candles, swings, width=swing_width)
    fvgs = find_fvgs(candles, require_displacement=True)
    obs = find_order_blocks(candles, events)
    pools = find_pools(swings, pip=pip, eq_tolerance_pips=eq_tolerance_pips)
    sweeps = find_sweeps(candles, pools)
    drange = find_dealing_range(candles, swings)
    breakers = find_breakers(candles, obs)
    # rejection blocks are only meaningful at known levels: swings + pool prices
    key_levels = [s.price for s in swings] + [p.price for p in pools]
    rbs = find_rejection_blocks(candles, key_levels=key_levels, tol=3 * pip)
    vis = find_volume_imbalances(candles, min_size=pip)
    sessions = all_session_ranges(candles)
    asia = asian_range(candles, anchor="kz")
    ipda = ipda_levels(candles)
    turtles = find_turtle_soups(candles, sweeps)
    crt = find_crt_setups(candles)
    quarterly = quarterly_context(candles)

    mtf = None
    if htf_timeframes:
        from .mtf import multi_timeframe_bias
        mtf = multi_timeframe_bias(candles, htf_timeframes)

    inv_fvgs = find_inversion_fvgs(candles, fvgs)
    bpr = find_bpr(fvgs)
    nested = find_nested_fvgs(fvgs)
    voids = find_liquidity_voids(candles)
    propulsion = find_propulsion_blocks(candles, obs)
    reclaimed = find_reclaimed_obs(candles, obs)
    rstate = range_state(candles)

    smt = []
    if smt_reference is not None:
        from .smt import find_smt_divergence
        smt = find_smt_divergence(candles, smt_reference, correlation=smt_correlation)
    blackout = None
    if news_events and candles:
        from .news import in_blackout
        blackout = in_blackout(candles[-1].ts, news_events)
    ndog = find_ndog(candles)
    nwog = find_nwog(candles)

    # tag every PD array with the side of equilibrium it sits on
    if drange is not None:
        for f in fvgs:
            f.pd_side = drange.classify(f.ce)
        for o in obs:
            o.pd_side = drange.classify(o.mt)
        for b in breakers:
            b.pd_side = drange.classify(b.mt)
        for rb in rbs:
            rb.pd_side = drange.classify((rb.low + rb.high) / 2)
        for vi in vis:
            vi.pd_side = drange.classify(vi.ce)

    result = Analysis(
        candles=candles,
        pip=pip,
        swings=swings,
        events=events,
        fvgs=fvgs,
        order_blocks=obs,
        pools=pools,
        sweeps=sweeps,
        breakers=breakers,
        rejection_blocks=rbs,
        volume_imbalances=vis,
        session_ranges=sessions,
        asian_range=asia,
        ipda=ipda,
        turtle_soups=turtles,
        crt_setups=crt,
        quarterly=quarterly,
        mtf=mtf,
        inversion_fvgs=inv_fvgs,
        bpr=bpr,
        nested_fvgs=nested,
        liquidity_voids=voids,
        propulsion_blocks=propulsion,
        range_state=rstate,
        reclaimed_obs=reclaimed,
        smt_divergences=smt,
        news_blackout=blackout,
        ndog=ndog,
        nwog=nwog,
        dealing_range=drange,
        bias=current_bias(events),
        killzone=active_killzone(candles[-1].ts) if candles else None,
    )
    # These depend on the assembled snapshot, so classify once it exists.
    from .setups import find_unicorns, find_diamonds
    result.unicorns = find_unicorns(result)
    result.diamonds = find_diamonds(result)
    result.stop_runs = classify_stop_runs(result)
    return result
