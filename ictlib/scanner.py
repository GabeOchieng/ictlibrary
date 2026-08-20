"""Signal scanner — the first tool built on the primitive library.

It encodes the classic ICT reversal setup:

    1. A liquidity SWEEP takes a pool (stops run beyond a high/low).
    2. An MSS (displaced CHoCH leaving an FVG) fires in the OPPOSITE direction
       shortly after — the algorithm's signature to reverse.
    3. Entry is the FVG left by that MSS (or the order block behind it), with
       consequent-encroachment / mean-threshold as the precise entry price.
    4. Stop sits beyond the sweep extreme; the first target is the opposite
       liquidity pool (the draw on liquidity).

Confluences add to a score: killzone active, HTF bias aligned, OTE zone,
equal-highs/lows pool swept.
"""

from __future__ import annotations

from typing import List, Optional

from .models import Signal, Sweep
from .analysis import Analysis, analyze
from .concepts.killzones import active_killzone, in_silver_bullet, ny_minutes
from .concepts.sessions import pre_open_range
from .concepts.ote import ote_from_leg, sd_projections, SD_OTE, measured_leg
from .setups import classify_models


def scan(
    analysis: Analysis,
    *,
    mss_window: int = 12,
    min_score: int = 2,
    require_htf_alignment: bool = False,
    stop_mode: str = "sweep",       # "sweep" (beyond swept extreme) | "structure"
    use_sd_targets: bool = True,     # add standard-deviation projection targets
) -> List[Signal]:
    """Produce signals from a completed :class:`Analysis`.

    ``require_htf_alignment`` drops signals whose direction conflicts with the
    multi-timeframe HTF bias (only applies when the analysis carries an ``mtf``
    context — see ``analyze(..., htf_timeframes=...)``).
    """
    signals: List[Signal] = []
    candles = analysis.candles
    por = pre_open_range(candles)   # for the Venom model (US-index pre-cash-open)

    for sweep in analysis.sweeps:
        # A BSL sweep (high taken) sets up a SHORT; SSL sweep sets up a LONG.
        want = "bear" if sweep.kind == "BSL" else "bull"

        mss = _first_mss_after(analysis, sweep.index, want, mss_window)
        if mss is None:
            continue

        entry_fvg = _fvg_for_event(analysis, mss.index, want)
        entry_ob = _ob_for_event(analysis, mss.index)
        if entry_fvg is None and entry_ob is None:
            continue

        if entry_fvg is not None:
            zone = (entry_fvg.low, entry_fvg.high)
            entry = entry_fvg.ce
        else:
            zone = (entry_ob.low, entry_ob.high)
            entry = entry_ob.mt

        buf = _stop_buffer(analysis, mss.index)
        if want == "bull":
            direction = "long"
            # structural stop = below the entry PD array; else beyond the sweep
            stop = (zone[0] - buf) if stop_mode == "structure" else (sweep.extreme - buf)
            targets = _targets(analysis, "BSL", entry, sweep, mss, "bull",
                               use_sd_targets)
        else:
            direction = "short"
            stop = (zone[1] + buf) if stop_mode == "structure" else (sweep.extreme + buf)
            targets = _targets(analysis, "SSL", entry, sweep, mss, "bear",
                               use_sd_targets)
        if require_htf_alignment and analysis.mtf is not None:
            if analysis.mtf.bias != "neutral" and not analysis.mtf.aligned(direction):
                continue

        reasons, score = _score(analysis, sweep, mss, entry_fvg, entry_ob,
                                direction, entry)

        if score < min_score:
            continue

        mss_ts = candles[mss.index].ts
        kz = active_killzone(mss_ts)
        bias_aligned = _bias_aligned(analysis, direction)
        # Venom: sweep took a pre-open-range bound and the MSS is in 09:30-11:00 NY.
        venom = False
        if por is not None:
            took = min(abs(sweep.level - por.high),
                       abs(sweep.level - por.low)) <= 3 * analysis.pip
            m = ny_minutes(mss_ts)
            venom = took and (9 * 60 + 30) <= m < 11 * 60

        models = classify_models(
            killzone=kz,
            sb_window=in_silver_bullet(mss_ts),
            sweep_killzone=active_killzone(candles[sweep.index].ts),
            bias_aligned=bias_aligned,
            has_fvg=mss.has_fvg,   # an MSS always leaves an FVG in the break
            venom=venom,
        )
        if models:
            reasons.append("models: " + ", ".join(models))

        signals.append(Signal(
            direction=direction,
            ts=mss_ts,
            index=mss.index,
            entry=entry,
            entry_zone=zone,
            stop=stop,
            targets=targets,
            reasons=reasons,
            score=score,
            killzone=kz,
            models=models,
        ))

    signals.sort(key=lambda s: (s.index, -s.score))
    return signals


def scan_candles(candles, **kw) -> List[Signal]:
    """Convenience: analyse and scan in one call."""
    analysis = analyze(candles, **{k: kw.pop(k) for k in list(kw)
                                   if k in ("swing_width", "pip",
                                            "eq_tolerance_pips")})
    return scan(analysis, **kw)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _bias_aligned(analysis, direction: str) -> bool:
    """True if the trade direction agrees with the HTF bias (if a multi-timeframe
    context is present) or otherwise the structural bias."""
    want = "bullish" if direction == "long" else "bearish"
    if analysis.mtf is not None and analysis.mtf.bias != "neutral":
        return analysis.mtf.bias == want
    return analysis.bias == want


def _first_mss_after(analysis, sweep_index, direction, window):
    for ev in analysis.events:
        if ev.kind != "MSS" or ev.direction != direction:
            continue
        if sweep_index < ev.index <= sweep_index + window:
            return ev
    return None


def _fvg_for_event(analysis, event_index, direction):
    best = None
    for f in analysis.fvgs:
        if f.direction != direction or f.mitigated:
            continue
        if event_index - 1 <= f.index <= event_index + 1:
            best = f
    return best


def _ob_for_event(analysis, event_index):
    for o in analysis.order_blocks:
        if o.event_index == event_index and not o.mitigated:
            return o
    return None


def _atr(candles, index, n=14) -> float:
    start = max(0, index - n)
    window = candles[start:index] or candles[:1]
    return sum(c.high - c.low for c in window) / len(window)


def _stop_buffer(analysis, index, mult: float = 0.35) -> float:
    """Volatility-aware stop buffer (a fraction of ATR), floored at 2 pips —
    keeps structural stops off the exact wick without being instrument-blind."""
    return max(mult * _atr(analysis.candles, index), 2 * analysis.pip)


def _targets(analysis, kind, entry, sweep, mss, leg_dir, use_sd, *, limit=4):
    """Draw-on-liquidity pools plus standard-deviation projection targets,
    nearest-first (concepts/28-fibonacci-levels/standard-deviation-projections)."""
    levels = list(_draw_on_liquidity(analysis, kind, entry, limit=99))
    if use_sd:
        candles = analysis.candles
        end = min(mss.index + 2, len(candles) - 1)
        # body-anchored measured leg (concepts/28/fib-anchoring)
        leg_start, leg_end = measured_leg(candles, sweep.index, end, leg_dir, "body")
        for price in sd_projections(leg_start, leg_end).values():
            if (price > entry) == (leg_dir == "bull"):
                levels.append(price)
    if leg_dir == "bull":
        out = sorted(set(lv for lv in levels if lv > entry))
    else:
        out = sorted(set(lv for lv in levels if lv < entry), reverse=True)
    return out[:limit]


def _draw_on_liquidity(analysis, kind, entry, *, limit: int = 3) -> List[float]:
    """The IPDA draw-on-liquidity set in the trade direction — pools plus
    session/Asian-range extremes and IPDA lookback levels (analysis.draw_on_liquidity).

    Returns up to ``limit`` targets, nearest first."""
    side = "up" if kind == "BSL" else "down"
    all_levels = analysis.draw_on_liquidity(side)
    if kind == "BSL":  # long targets: levels above entry, ascending
        levels = sorted(lv for lv in all_levels if lv > entry)
    else:              # short targets: levels below entry, descending
        levels = sorted((lv for lv in all_levels if lv < entry), reverse=True)
    return levels[:limit]


def _score(analysis, sweep, mss, fvg, ob, direction, entry):
    reasons = [
        f"{sweep.kind} liquidity sweep @ {sweep.level:.5f}",
        f"MSS {mss.direction} (displacement + FVG) @ {mss.level:.5f}",
    ]
    score = 2  # sweep + MSS are the core

    if fvg is not None:
        reasons.append(f"entry FVG {fvg.low:.5f}-{fvg.high:.5f} (CE {fvg.ce:.5f})")
    if ob is not None:
        reasons.append(f"order block {ob.low:.5f}-{ob.high:.5f} (MT {ob.mt:.5f})")

    kz = active_killzone(analysis.candles[mss.index].ts)
    if kz:
        reasons.append(f"in {kz} killzone")
        score += 1

    want_bias = "bullish" if direction == "long" else "bearish"
    if analysis.bias == want_bias:
        reasons.append(f"HTF bias {analysis.bias} aligned")
        score += 1

    # OTE: measured leg = sweep extreme -> MSS break level
    leg_dir = "bull" if direction == "long" else "bear"
    ote = ote_from_leg(sweep.extreme, mss.level, leg_dir)
    if ote.contains(entry):
        reasons.append("entry inside OTE 0.62-0.79")
        score += 1

    pool = next((p for p in analysis.pools if p.index == sweep.pool_index), None)
    if pool and pool.label in ("EQH", "EQL"):
        reasons.append(f"swept {pool.label} (dense pool)")
        score += 1

    # Premium/discount discipline: longs should originate at a discount, shorts
    # at a premium (concepts/05-pd-arrays). Reward alignment, flag a violation.
    dr = analysis.dealing_range
    if dr is not None:
        side = dr.classify(entry)
        want_side = "discount" if direction == "long" else "premium"
        if side == want_side:
            reasons.append(f"entry at {side} (EQ {dr.eq:.5f}) — correct side of range")
            score += 1
        elif side != "equilibrium":
            reasons.append(f"⚠ entry at {side} for a {direction} — against PD discipline")

    # Stacked imbalance: a volume imbalance or breaker overlapping the entry zone
    # adds conviction (concepts/06-fair-value-gaps/volume-imbalance, 08-breaker-blocks).
    want_dir = "bull" if direction == "long" else "bear"
    if any(vi.direction == want_dir and vi.low <= entry <= vi.high
           for vi in analysis.volume_imbalances):
        reasons.append("stacked volume imbalance at entry")
        score += 1
    if any(b.direction == want_dir and b.low <= entry <= b.high
           for b in analysis.breakers):
        reasons.append("breaker block confluence at entry")
        score += 1

    # Turtle Soup: the sweep resolved as a named failed breakout.
    if any(ts.index == sweep.index for ts in analysis.turtle_soups):
        reasons.append("turtle soup (failed breakout confirmed)")
        score += 1

    # Power of Three / Quarterly Theory: manipulation & distribution quarters are
    # the sweep + true-move phases that favour this setup.
    q = analysis.quarterly
    if q and q.phase in ("manipulation", "distribution"):
        reasons.append(f"PO3 {q.phase} phase ({q.daily_quarter})")
        score += 1

    # True Day Open: intraday discount for longs / premium for shorts.
    if q and q.tdo is not None:
        want_tdo = "discount" if direction == "long" else "premium"
        if q.price_vs_tdo == want_tdo:
            reasons.append(f"intraday {want_tdo} vs TDO {q.tdo:.5f}")
            score += 1

    # Multi-timeframe HTF bias (top-down). Aligned adds conviction; a conflict
    # against a clear HTF bias is flagged.
    mtf = analysis.mtf
    if mtf is not None and mtf.bias != "neutral":
        stack = "+".join(r.label for r in mtf.reads) or "HTF"
        if mtf.aligned(direction):
            reasons.append(f"HTF bias {mtf.bias} aligned ({stack})")
            score += 1
        else:
            reasons.append(f"⚠ against HTF bias {mtf.bias} ({stack})")

    # Unicorn A+ zone overlapping the entry (breaker + nested FVG + bias + sweep).
    want_dir2 = "bull" if direction == "long" else "bear"
    if any(u.direction == want_dir2 and u.low <= entry <= u.high
           for u in analysis.unicorns):
        reasons.append("Unicorn A+ zone at entry (breaker + nested FVG)")
        score += 2

    # Diamond pattern: both-side liquidity swept before this break.
    if any(d["break_index"] == mss.index and d["direction"] == want_dir2
           for d in analysis.diamonds):
        reasons.append("diamond (both-side sweep before break)")
        score += 1

    # Stop-run classification (concepts/29-stop-runs): name the PD array the
    # sweep ran into.
    sr = next((r for r in analysis.stop_runs if r["sweep_index"] == sweep.index), None)
    if sr is not None:
        reasons.append(f"stop-run into {sr['into']}")

    # SMT divergence confirmation (intermarket / correlated pair).
    if any(d.direction == want_dir2 for d in analysis.smt_divergences[-3:]):
        reasons.append("SMT divergence confirms direction")
        score += 1

    # News blackout — flag entries inside a high-impact no-trade window.
    if analysis.news_blackout is not None:
        reasons.append(f"⚠ news blackout ({analysis.news_blackout.name})")

    return reasons, score
