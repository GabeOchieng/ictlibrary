"""OandaBroker — places bracket orders via the OANDA v20 REST API.

Requires an account id and token. A LIVE broker: the Trader will not send orders
to it unless dry_run=False and allow_live=True.

    export OANDA_API_KEY="token"
    export OANDA_ACCOUNT_ID="xxx-xxx-xxxxxxxx-xxx"
    export OANDA_ENV="practice"   # or "live"
"""

from __future__ import annotations

import os
from typing import List, Optional

from .base import Broker, Account, OrderResult, BrokerOrder, Position

_HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaBroker(Broker):
    live = True

    def __init__(self, api_key=None, account_id=None, env=None, *, timeout=20.0):
        self.api_key = api_key or os.environ.get("OANDA_API_KEY")
        self.account_id = account_id or os.environ.get("OANDA_ACCOUNT_ID")
        self.env = (env or os.environ.get("OANDA_ENV") or "practice").lower()
        if not self.api_key or not self.account_id:
            raise RuntimeError("Need OANDA_API_KEY and OANDA_ACCOUNT_ID.")
        self.host = _HOSTS[self.env]
        self.timeout = timeout
        # OANDA is a live venue; env == "live" means real money.
        self.live = self.env == "live"

    def _req(self, method, path, json=None):
        import requests
        url = f"{self.host}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        return requests.request(method, url, headers=headers, json=json,
                                timeout=self.timeout)

    def account(self) -> Account:
        r = self._req("GET", f"/v3/accounts/{self.account_id}/summary")
        a = r.json().get("account", {})
        return Account(balance=float(a.get("balance", 0)),
                       equity=float(a.get("NAV", a.get("balance", 0))),
                       currency=a.get("currency", "USD"),
                       open_positions=int(a.get("openPositionCount", 0)))

    def place_bracket(self, symbol, side, lots, *, stop, target,
                      entry=None, type="market") -> OrderResult:
        units = int(round(lots * 100_000)) * (1 if side == "buy" else -1)
        order = {
            "units": str(units),
            "instrument": symbol,
            "type": "MARKET" if type == "market" else "LIMIT",
            "timeInForce": "FOK" if type == "market" else "GTC",
            "positionFill": "DEFAULT",
        }
        if type == "limit" and entry is not None:
            order["price"] = f"{entry:.5f}"
        if stop is not None:
            order["stopLossOnFill"] = {"price": f"{stop:.5f}", "timeInForce": "GTC"}
        if target is not None:
            order["takeProfitOnFill"] = {"price": f"{target:.5f}", "timeInForce": "GTC"}
        try:
            r = self._req("POST", f"/v3/accounts/{self.account_id}/orders",
                          json={"order": order})
        except Exception as exc:
            return OrderResult(False, message=f"request failed: {exc}")
        if r.status_code not in (200, 201):
            return OrderResult(False, message=f"OANDA {r.status_code}: {r.text[:200]}")
        data = r.json()
        oid = (data.get("orderCreateTransaction") or {}).get("id")
        return OrderResult(True, id=oid, message="submitted", raw=data)

    def positions(self) -> List[Position]:
        r = self._req("GET", f"/v3/accounts/{self.account_id}/openPositions")
        out = []
        for p in r.json().get("positions", []):
            long_units = float(p.get("long", {}).get("units", 0))
            side = "buy" if long_units > 0 else "sell"
            book = p["long"] if long_units > 0 else p["short"]
            out.append(Position(id=p["instrument"], symbol=p["instrument"], side=side,
                                lots=abs(float(book.get("units", 0))) / 100_000,
                                entry_price=float(book.get("averagePrice", 0))))
        return out

    def orders(self) -> List[BrokerOrder]:
        r = self._req("GET", f"/v3/accounts/{self.account_id}/pendingOrders")
        out = []
        for o in r.json().get("orders", []):
            out.append(BrokerOrder(id=o.get("id", ""), symbol=o.get("instrument", ""),
                                   side="buy" if float(o.get("units", 0)) > 0 else "sell",
                                   lots=abs(float(o.get("units", 0))) / 100_000,
                                   type=o.get("type", "").lower(), status="pending"))
        return out
