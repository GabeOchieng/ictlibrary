"""Named ICT models (concepts/31-models, 11-silver-bullet, 13-judas-swing).

These are not new detections — they are recognized *compositions* of the
primitives the scanner already finds. A single sweep -> displacement+FVG ->
entry sequence is classified into the named models whose extra conditions it
also satisfies:

    ICT 2022 Model : killzone active + HTF bias + sweep + displacement+FVG + CE entry
    Silver Bullet  : the 2022 model, inside a 03-04 / 10-11 / 14-15 NY SB window
    Judas Swing    : a session-open sweep (London/NY AM) that reverses with bias

The Unicorn is detected separately: a breaker with a nested same-direction FVG,
HTF-bias aligned, with a prior sweep.
"""

from __future__ import annotations

from typing import List

from .models import Unicorn


def classify_models(
    *,
    killzone,          # active killzone at the MSS bar (or None)
    sb_window: bool,   # inside a silver-bullet window at the MSS bar
    sweep_killzone,    # active killzone at the sweep bar (or None)
    bias_aligned: bool,
    has_fvg: bool,
) -> List[str]:
    """Return the named models this signal qualifies as."""
    out: List[str] = []
    base = bias_aligned and has_fvg and killzone is not None
    if base:
        out.append("ICT 2022 Model")
    if base and sb_window:
        out.append("Silver Bullet")
    if bias_aligned and sweep_killzone in ("London Open", "NY AM"):
        out.append("Judas Swing")
    return out


def find_unicorns(analysis) -> List[Unicorn]:
    """Detect Unicorn-grade zones: breaker + nested FVG + HTF bias + prior sweep."""
    out: List[Unicorn] = []
    for br in analysis.breakers:
        want = "bullish" if br.direction == "bull" else "bearish"
        if analysis.mtf is not None and analysis.mtf.bias != "neutral":
            bias_ok = analysis.mtf.bias == want
        else:
            bias_ok = analysis.bias == want
        if not bias_ok:
            continue
        prior_sweep = any(s.index < br.ob_index for s in analysis.sweeps)
        if not prior_sweep:
            continue
        for f in analysis.fvgs:
            if f.direction == br.direction and br.low <= f.ce <= br.high:
                out.append(Unicorn(
                    index=br.index, ts=br.ts, direction=br.direction,
                    low=br.low, high=br.high,
                    breaker_index=br.break_index, fvg_index=f.index,
                ))
                break
    return out
