"""Risk management (concepts/32-risk-management).

Pure math the scanner and backtester share:

    position_size = risk_$ / sl_distance_$
                  = (equity * risk_pct) / (sl_pips * pip_value)

    R = (target - entry) / (entry - stop)      # works for longs and shorts

Structural stop placement (stop-placement-by-pd-array) is already done where the
signals are built (stop beyond the sweep / PD-array invalidation + buffer).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

# $ per pip per standard lot, by instrument (concepts/32/position-sizing table).
PIP_VALUE_PER_LOT = {
    "EUR_USD": 10.0, "GBP_USD": 10.0, "AUD_USD": 10.0, "NZD_USD": 10.0,
    "USD_JPY": 6.7, "USD_CHF": 11.0, "USD_CAD": 7.5,
    "XAU_USD": 10.0,      # per "pip" = 0.10
    "NAS100": 20.0,       # NQ, $/point per contract
    "SPX500": 50.0,       # ES, $/point per contract
}
DEFAULT_PIP_VALUE = 10.0

# Partial-take schedules: (fraction, R-target). The remaining fraction is the
# runner, exited at the furthest signal target (or trailed).
PARTIAL_SCHEDULES = {
    "conservative": [(0.50, 1.0), (0.25, 2.0)],   # runner 0.25
    "standard":     [(0.33, 2.0), (0.33, 4.0)],   # runner 0.34
    "runner":       [(0.25, 1.0), (0.25, 3.0)],   # runner 0.50
    "single":       [],                            # single TP, no partials
}


@dataclass
class RiskParams:
    equity: float = 10_000.0
    risk_pct: float = 0.01          # 1% risk per trade
    pip_value: float = DEFAULT_PIP_VALUE

    @property
    def risk_dollars(self) -> float:
        return self.equity * self.risk_pct


def pips(distance_price: float, pip: float) -> float:
    return abs(distance_price) / pip if pip else 0.0


def position_size(
    entry: float,
    stop: float,
    pip: float,
    params: RiskParams,
) -> float:
    """Standard-lot size that risks exactly ``risk_pct`` of equity given the SL."""
    sl_pips = pips(entry - stop, pip)
    denom = sl_pips * params.pip_value
    return params.risk_dollars / denom if denom else 0.0


def r_multiple(entry: float, stop: float, price: float) -> float:
    """R at ``price`` relative to the entry/stop. Positive = in profit for the
    trade's direction (works for both longs and shorts)."""
    denom = entry - stop
    return (price - entry) / denom if denom else 0.0


def price_at_r(entry: float, stop: float, r: float) -> float:
    """The price that corresponds to a given R multiple."""
    return entry + r * (entry - stop)


@dataclass
class SizedSignal:
    direction: str
    entry: float
    stop: float
    lots: float
    risk_dollars: float
    sl_pips: float
    target_rs: List[float]

    def to_dict(self) -> dict:
        return {
            "direction": self.direction, "entry": self.entry, "stop": self.stop,
            "lots": round(self.lots, 4), "risk_dollars": round(self.risk_dollars, 2),
            "sl_pips": round(self.sl_pips, 1),
            "target_rs": [round(r, 2) for r in self.target_rs],
        }


def size_signal(signal, pip: float, params: Optional[RiskParams] = None) -> SizedSignal:
    """Attach position size + per-target R multiples to a :class:`Signal`."""
    params = params or RiskParams()
    lots = position_size(signal.entry, signal.stop, pip, params)
    return SizedSignal(
        direction=signal.direction,
        entry=signal.entry,
        stop=signal.stop,
        lots=lots,
        risk_dollars=params.risk_dollars,
        sl_pips=pips(signal.entry - signal.stop, pip),
        target_rs=[r_multiple(signal.entry, signal.stop, t) for t in signal.targets],
    )


def pip_value_for(instrument: str) -> float:
    return PIP_VALUE_PER_LOT.get(instrument, DEFAULT_PIP_VALUE)
