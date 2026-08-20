"""PaperBroker — an in-memory broker for paper trading and dry runs.

Accepts bracket orders and processes them against a price feed (candles): limit
entries fill when price trades through them; open positions close on stop-loss
or take-profit. P&L is tracked in account currency using the pip value, and in R
multiples. No network, no risk — the safe way to run the strategy live.
"""

from __future__ import annotations

import itertools
from typing import List, Optional

from ..models import Candle
from .base import Broker, Account, OrderResult, BrokerOrder, Position


class PaperBroker(Broker):
    live = False

    def __init__(self, balance: float = 10_000.0, *, pip: float = 0.0001,
                 pip_value: float = 10.0, currency: str = "USD"):
        self.balance = balance
        self.pip = pip
        self.pip_value = pip_value
        self.currency = currency
        self._orders: List[BrokerOrder] = []
        self._positions: List[Position] = []
        self._ids = itertools.count(1)

    # -- Broker API -------------------------------------------------------- #
    def account(self) -> Account:
        equity = self.balance + sum(self._unrealised(p) for p in self._open())
        return Account(balance=round(self.balance, 2), equity=round(equity, 2),
                       currency=self.currency, open_positions=len(self._open()))

    def place_bracket(self, symbol, side, lots, *, stop, target,
                      entry=None, type="market") -> OrderResult:
        if side not in ("buy", "sell"):
            return OrderResult(False, message=f"bad side {side!r}")
        oid = f"O{next(self._ids)}"
        order = BrokerOrder(id=oid, symbol=symbol, side=side, lots=lots,
                            stop=stop, target=target, entry=entry, type=type)
        if type == "market":
            # market orders are opened at the next feed price; park as pending
            order.entry = None
        self._orders.append(order)
        return OrderResult(True, id=oid, message="accepted")

    def orders(self) -> List[BrokerOrder]:
        return list(self._orders)

    def positions(self) -> List[Position]:
        return list(self._positions)

    def cancel(self, order_id) -> OrderResult:
        for o in self._orders:
            if o.id == order_id and o.status == "pending":
                o.status = "cancelled"
                return OrderResult(True, id=order_id, message="cancelled")
        return OrderResult(False, message="order not pending")

    def close(self, position_id, price=None) -> OrderResult:
        for p in self._positions:
            if p.id == position_id and p.status == "open":
                self._close(p, price if price is not None else p.entry_price, "manual")
                return OrderResult(True, id=position_id, message="closed")
        return OrderResult(False, message="position not open")

    # -- price feed -------------------------------------------------------- #
    def feed(self, candle: Candle) -> None:
        """Advance the simulation by one bar: fill pending orders, then manage
        open positions (stop checked before target — worst case)."""
        for o in list(self._orders):
            if o.status != "pending":
                continue
            fill = self._fill_price(o, candle)
            if fill is not None:
                o.status = "filled"
                self._positions.append(Position(
                    id=o.id, symbol=o.symbol, side=o.side, lots=o.lots,
                    entry_price=fill, stop=o.stop, target=o.target))

        for p in self._open():
            self._manage(p, candle)

    # -- internals --------------------------------------------------------- #
    def _fill_price(self, o: BrokerOrder, c: Candle) -> Optional[float]:
        if o.entry is None:                     # market order -> fill at open
            return c.open
        if c.low <= o.entry <= c.high:          # limit touched
            return o.entry
        return None

    def _manage(self, p: Position, c: Candle) -> None:
        if p.side == "buy":
            if p.stop is not None and c.low <= p.stop:
                self._close(p, p.stop, "stop")
            elif p.target is not None and c.high >= p.target:
                self._close(p, p.target, "target")
        else:
            if p.stop is not None and c.high >= p.stop:
                self._close(p, p.stop, "stop")
            elif p.target is not None and c.low <= p.target:
                self._close(p, p.target, "target")

    def _close(self, p: Position, price: float, reason: str) -> None:
        p.status = "closed"
        p.exit_price = price
        p.exit_reason = reason
        p.pnl = round(self._pnl(p, price), 2)
        if p.stop is not None and (p.entry_price - p.stop) != 0:
            p.r = round((price - p.entry_price) / (p.entry_price - p.stop), 3)
        self.balance += p.pnl

    def _pnl(self, p: Position, price: float) -> float:
        sign = 1 if p.side == "buy" else -1
        pips = (price - p.entry_price) / self.pip * sign
        return pips * self.pip_value * p.lots

    def _unrealised(self, p: Position) -> float:
        return 0.0                              # mark-to-open only when fed

    def _open(self) -> List[Position]:
        return [p for p in self._positions if p.status == "open"]
