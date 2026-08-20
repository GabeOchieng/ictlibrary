"""Trader — routes scanner signals to a broker as sized bracket orders.

Sizes each signal with the risk module, builds an entry + stop + target bracket,
and submits it. Guards keep it safe:
- ``dry_run`` (default) logs the order and never sends it.
- Placing against a live broker requires ``allow_live=True`` explicitly.
- Each signal index is submitted at most once.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from ..models import Signal
from ..risk import RiskParams, position_size
from .base import Broker, OrderResult


class Trader:
    def __init__(
        self,
        broker: Broker,
        *,
        instrument: str,
        pip: float,
        risk: Optional[RiskParams] = None,
        min_score: int = 3,
        entry_type: str = "limit",      # "limit" | "market"
        target_index: int = 0,          # which signal target to use as TP
        dry_run: bool = True,
        allow_live: bool = False,
        logger: Optional[Callable[[str], None]] = None,
    ):
        self.broker = broker
        self.instrument = instrument
        self.pip = pip
        self.risk = risk or RiskParams()
        self.min_score = min_score
        self.entry_type = entry_type
        self.target_index = target_index
        self.dry_run = dry_run
        self.allow_live = allow_live
        self.log = logger or (lambda m: None)
        self._seen: set[int] = set()

        if broker.live and not dry_run and not allow_live:
            raise PermissionError(
                "Refusing to trade a LIVE broker without allow_live=True. "
                "Set dry_run=True to simulate, or allow_live=True to go live."
            )

    def submit(self, signal: Signal) -> Optional[OrderResult]:
        if signal.score < self.min_score or signal.index in self._seen:
            return None
        if not signal.targets:
            return None
        self._seen.add(signal.index)

        side = "buy" if signal.direction == "long" else "sell"
        lots = position_size(signal.entry, signal.stop, self.pip, self.risk)
        entry = signal.entry if self.entry_type == "limit" else None
        idx = min(self.target_index, len(signal.targets) - 1)
        target = signal.targets[idx]

        desc = (f"{side.upper()} {self.instrument} {lots:.3f} lots "
                f"@ {'MKT' if entry is None else f'{entry:.5f}'} "
                f"SL {signal.stop:.5f} TP {target:.5f} (score {signal.score}"
                f"{', ' + ', '.join(signal.models) if signal.models else ''})")

        if self.dry_run:
            self.log(f"[DRY-RUN] {desc}")
            return OrderResult(True, message=f"dry-run: {desc}")

        self.log(f"[LIVE] {desc}")
        return self.broker.place_bracket(
            self.instrument, side, lots, stop=signal.stop, target=target,
            entry=entry, type=self.entry_type)

    def process(self, signals: List[Signal]) -> List[OrderResult]:
        out = []
        for s in signals:
            res = self.submit(s)
            if res is not None:
                out.append(res)
        return out
