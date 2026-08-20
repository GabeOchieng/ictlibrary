"""AlpacaBroker — places bracket orders via the Alpaca Trading API.

Requires trading keys. Uses the paper endpoint by default; the live endpoint is
real money. The Trader will not send orders unless dry_run=False and
allow_live=True.

    export APCA_API_KEY_ID="key"
    export APCA_API_SECRET_KEY="secret"
    export ALPACA_TRADING_ENV="paper"   # or "live"
"""

from __future__ import annotations

import os
from typing import List, Optional

from .base import Broker, Account, OrderResult, BrokerOrder, Position

_HOSTS = {
    "paper": "https://paper-api.alpaca.markets",
    "live": "https://api.alpaca.markets",
}


class AlpacaBroker(Broker):
    live = True

    def __init__(self, key_id=None, secret_key=None, env=None, *, timeout=20.0):
        self.key_id = key_id or os.environ.get("APCA_API_KEY_ID")
        self.secret_key = secret_key or os.environ.get("APCA_API_SECRET_KEY")
        self.env = (env or os.environ.get("ALPACA_TRADING_ENV") or "paper").lower()
        if not self.key_id or not self.secret_key:
            raise RuntimeError("Need APCA_API_KEY_ID and APCA_API_SECRET_KEY.")
        self.host = _HOSTS[self.env]
        self.timeout = timeout
        self.live = self.env == "live"

    def _headers(self):
        return {"APCA-API-KEY-ID": self.key_id,
                "APCA-API-SECRET-KEY": self.secret_key}

    def _req(self, method, path, json=None):
        import requests
        return requests.request(method, f"{self.host}{path}",
                                headers=self._headers(), json=json, timeout=self.timeout)

    def account(self) -> Account:
        a = self._req("GET", "/v2/account").json()
        return Account(balance=float(a.get("cash", 0)),
                       equity=float(a.get("equity", 0)),
                       currency=a.get("currency", "USD"))

    def place_bracket(self, symbol, side, lots, *, stop, target,
                      entry=None, type="market") -> OrderResult:
        # For Alpaca, "lots" is interpreted as share/contract quantity.
        order = {
            "symbol": symbol,
            "qty": str(abs(lots)),
            "side": "buy" if side == "buy" else "sell",
            "type": "market" if type == "market" else "limit",
            "time_in_force": "gtc",
            "order_class": "bracket",
        }
        if type == "limit" and entry is not None:
            order["limit_price"] = f"{entry:.2f}"
        if stop is not None:
            order["stop_loss"] = {"stop_price": f"{stop:.2f}"}
        if target is not None:
            order["take_profit"] = {"limit_price": f"{target:.2f}"}
        try:
            r = self._req("POST", "/v2/orders", json=order)
        except Exception as exc:
            return OrderResult(False, message=f"request failed: {exc}")
        if r.status_code not in (200, 201):
            return OrderResult(False, message=f"Alpaca {r.status_code}: {r.text[:200]}")
        data = r.json()
        return OrderResult(True, id=data.get("id"), message="submitted", raw=data)

    def positions(self) -> List[Position]:
        out = []
        for p in self._req("GET", "/v2/positions").json():
            out.append(Position(id=p["symbol"], symbol=p["symbol"],
                                side="buy" if p.get("side") == "long" else "sell",
                                lots=abs(float(p.get("qty", 0))),
                                entry_price=float(p.get("avg_entry_price", 0))))
        return out

    def orders(self) -> List[BrokerOrder]:
        out = []
        for o in self._req("GET", "/v2/orders?status=open").json():
            out.append(BrokerOrder(id=o.get("id", ""), symbol=o.get("symbol", ""),
                                   side=o.get("side", ""),
                                   lots=abs(float(o.get("qty", 0))),
                                   type=o.get("type", ""), status="pending"))
        return out
