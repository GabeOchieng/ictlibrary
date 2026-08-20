"""Stop-run classification (concepts/29-stop-runs).

A stop run is a liquidity sweep; the high-conviction variants name the PD array
the post-sweep displacement leaves behind:

    stop-run-into-FVG      — sweep then a displacement FVG (the entry zone)
    stop-run-into-OB       — sweep then an order block
    stop-run-into-breaker  — sweep into a flipped breaker zone

Classifies each sweep by the nearest PD array that formed just after it.
"""

from __future__ import annotations

from typing import List, Dict


def classify_stop_runs(analysis, *, window: int = 5) -> List[Dict]:
    """Label each sweep with the PD array it ran into, if any."""
    out: List[Dict] = []
    for sw in analysis.sweeps:
        want = "bull" if sw.kind == "SSL" else "bear"
        into = None
        fvg = next((f for f in analysis.fvgs
                    if f.direction == want and sw.index <= f.index <= sw.index + window), None)
        ob = next((o for o in analysis.order_blocks
                   if o.direction == want and sw.index <= o.index <= sw.index + window), None)
        breaker = next((b for b in analysis.breakers
                        if b.direction == want and sw.index <= b.break_index <= sw.index + window), None)
        if fvg is not None:
            into = "FVG"
        elif ob is not None:
            into = "OB"
        elif breaker is not None:
            into = "breaker"
        if into:
            out.append({"sweep_index": sw.index, "kind": sw.kind,
                        "direction": want, "into": into})
    return out
