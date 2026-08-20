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
from .concepts.killzones import active_killzone
from .concepts.ote import ote_from_leg


def scan(
    analysis: Analysis,
    *,
    mss_window: int = 12,
    min_score: int = 2,
) -> List[Signal]:
    """Produce signals from a completed :class:`Analysis`."""
    signals: List[Signal] = []
    candles = analysis.candles

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

        if want == "bull":
            direction = "long"
            if entry_fvg is not None:
                zone = (entry_fvg.low, entry_fvg.high)
                entry = entry_fvg.ce
            else:
                zone = (entry_ob.low, entry_ob.high)
                entry = entry_ob.mt
            stop = sweep.extreme - 2 * analysis.pip
            targets = _draw_on_liquidity(analysis, "BSL", entry)
        else:
            direction = "short"
            if entry_fvg is not None:
                zone = (entry_fvg.low, entry_fvg.high)
                entry = entry_fvg.ce
            else:
                zone = (entry_ob.low, entry_ob.high)
                entry = entry_ob.mt
            stop = sweep.extreme + 2 * analysis.pip
            targets = _draw_on_liquidity(analysis, "SSL", entry)
        reasons, score = _score(analysis, sweep, mss, entry_fvg, entry_ob,
                                direction, entry)

        if score < min_score:
            continue

        signals.append(Signal(
            direction=direction,
            ts=candles[mss.index].ts,
            index=mss.index,
            entry=entry,
            entry_zone=zone,
            stop=stop,
            targets=targets,
            reasons=reasons,
            score=score,
            killzone=active_killzone(candles[mss.index].ts),
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


def _draw_on_liquidity(analysis, kind, entry, *, limit: int = 3) -> List[float]:
    """Opposite-side pools in the trade direction — the draw on liquidity.

    Returns up to ``limit`` targets, nearest first (T1 = nearest pool, then the
    next pools out toward the major old high/low)."""
    candidates = [p for p in analysis.pools if p.kind == kind and not p.swept]
    if kind == "BSL":  # long targets: pools above entry, ascending
        levels = sorted(p.price for p in candidates if p.price > entry)
    else:              # short targets: pools below entry, descending
        levels = sorted((p.price for p in candidates if p.price < entry),
                        reverse=True)
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

    return reasons, score
