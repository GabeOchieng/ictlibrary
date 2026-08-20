"""Alpaca Market Data (v2) candle client.

Pulls US-equity or crypto OHLCV bars from Alpaca and returns the library's
:class:`Candle` objects. Requires an Alpaca account and API keys.

    export APCA_API_KEY_ID="your-key"
    export APCA_API_SECRET_KEY="your-secret"
    export ALPACA_FEED="iex"      # or "sip" (paid) for stocks

Only the standard library + ``requests`` are used; ``requests`` is imported
lazily so the rest of the library has no hard dependency on it.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional

from ..models import Candle

_STOCK_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
_CRYPTO_URL = "https://data.alpaca.markets/v1beta3/crypto/us/bars"

# OANDA-style granularity codes -> Alpaca timeframe strings
_TF = {
    "M1": "1Min", "M5": "5Min", "M15": "15Min", "M30": "30Min",
    "H1": "1Hour", "H4": "4Hour", "D": "1Day", "W": "1Week",
    # pass-through for native Alpaca strings
    "1Min": "1Min", "5Min": "5Min", "15Min": "15Min", "30Min": "30Min",
    "1Hour": "1Hour", "4Hour": "4Hour", "1Day": "1Day", "1Week": "1Week",
}


class AlpacaError(RuntimeError):
    pass


class AlpacaClient:
    def __init__(
        self,
        key_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        *,
        feed: Optional[str] = None,
        timeout: float = 20.0,
    ):
        self.key_id = key_id or os.environ.get("APCA_API_KEY_ID")
        self.secret_key = secret_key or os.environ.get("APCA_API_SECRET_KEY")
        if not self.key_id or not self.secret_key:
            raise AlpacaError(
                "No Alpaca credentials. Set APCA_API_KEY_ID and "
                "APCA_API_SECRET_KEY, or pass key_id=/secret_key=."
            )
        self.feed = feed or os.environ.get("ALPACA_FEED") or "iex"
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "APCA-API-KEY-ID": self.key_id,
            "APCA-API-SECRET-KEY": self.secret_key,
        }

    def get_candles(
        self,
        symbol: str,
        granularity: str = "M15",
        count: int = 300,
        *,
        asset: str = "stocks",   # "stocks" | "crypto"
    ) -> List[Candle]:
        """Fetch ``count`` bars for ``symbol`` (e.g. ``AAPL`` or ``BTC/USD``)."""
        import requests  # lazy

        tf = _TF.get(granularity, granularity)
        if asset == "crypto":
            url = _CRYPTO_URL
            params = {"symbols": symbol, "timeframe": tf, "limit": count}
        else:
            url = _STOCK_URL.format(symbol=symbol)
            params = {"timeframe": tf, "limit": count, "feed": self.feed,
                      "adjustment": "raw"}
        try:
            resp = requests.get(url, params=params, headers=self._headers(),
                                timeout=self.timeout)
        except Exception as exc:
            raise AlpacaError(f"Alpaca request failed: {exc}") from exc
        if resp.status_code != 200:
            raise AlpacaError(f"Alpaca {resp.status_code}: {resp.text[:200]}")

        payload = resp.json()
        if asset == "crypto":
            bars = payload.get("bars", {}).get(symbol, [])
        else:
            bars = payload.get("bars", []) or []

        out: List[Candle] = []
        for b in bars:
            ts = datetime.fromisoformat(b["t"].replace("Z", "+00:00"))
            out.append(Candle(
                ts=ts.astimezone(timezone.utc),
                open=float(b["o"]), high=float(b["h"]),
                low=float(b["l"]), close=float(b["c"]),
                volume=float(b.get("v", 0)),
            ))
        out.sort(key=lambda c: c.ts)
        return out
