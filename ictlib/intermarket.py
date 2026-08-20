"""Intermarket / order-flow reads (concepts/03-order-flow).

Order flow in ICT includes intermarket confirmation: the US Dollar Index (DXY)
and correlated pairs. A USD-quote pair (EURUSD, GBPUSD) is inversely correlated
with DXY, so a DXY SMT divergence against the pair is a directional-flow signal.

These need an external reference series; they are not run automatically.
"""

from __future__ import annotations

from typing import List

from .models import Candle, SMTDivergence
from .smt import find_smt_divergence


def dollar_index_smt(
    pair_candles: List[Candle],
    dxy_candles: List[Candle],
    *,
    width: int = 2,
) -> List[SMTDivergence]:
    """SMT divergence between a USD-quote pair and DXY (inverse correlation)."""
    return find_smt_divergence(pair_candles, dxy_candles,
                               correlation="negative", width=width)


def intermarket_bias(divergences: List[SMTDivergence]) -> str:
    """Aggregate the most recent intermarket SMT into a directional lean."""
    if not divergences:
        return "neutral"
    last = divergences[-1]
    return "bullish" if last.direction == "bull" else "bearish"
