"""Broker abstraction for the execution layer.

A broker turns a sized bracket order (entry + stop-loss + take-profit) into a
real or simulated position. Concrete implementations: PaperBroker (in-memory
simulation), OandaBroker (v20), AlpacaBroker.

Everything is bracket-first — ICT stops and targets are structural, so an order
is never placed without its SL/TP.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Account:
    balance: float
    equity: float
    currency: str = "USD"
    open_positions: int = 0


@dataclass
class OrderResult:
    ok: bool
    id: Optional[str] = None
    message: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class BrokerOrder:
    id: str
    symbol: str
    side: str                       # "buy" | "sell"
    lots: float
    stop: Optional[float] = None
    target: Optional[float] = None
    entry: Optional[float] = None   # None = market
    type: str = "market"            # "market" | "limit"
    status: str = "pending"         # pending | filled | cancelled
    created: Optional[datetime] = None


@dataclass
class Position:
    id: str
    symbol: str
    side: str                       # "buy" | "sell"
    lots: float
    entry_price: float
    stop: Optional[float] = None
    target: Optional[float] = None
    status: str = "open"            # open | closed
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    r: float = 0.0


class Broker(ABC):
    """Minimal broker contract the Trader depends on."""

    live: bool = False              # True for real-money brokers

    @abstractmethod
    def account(self) -> Account: ...

    @abstractmethod
    def place_bracket(
        self,
        symbol: str,
        side: str,
        lots: float,
        *,
        stop: Optional[float],
        target: Optional[float],
        entry: Optional[float] = None,
        type: str = "market",
    ) -> OrderResult: ...

    @abstractmethod
    def positions(self) -> List[Position]: ...

    @abstractmethod
    def orders(self) -> List[BrokerOrder]: ...

    def cancel(self, order_id: str) -> OrderResult:   # optional
        return OrderResult(False, message="cancel not supported")

    def close(self, position_id: str, price: Optional[float] = None) -> OrderResult:
        return OrderResult(False, message="close not supported")
