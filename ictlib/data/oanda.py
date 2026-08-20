"""OANDA v20 REST candle client.

Pulls forex OHLCV from OANDA and returns the library's :class:`Candle` objects.
Requires an OANDA practice or live account and an API token.

    export OANDA_API_KEY="your-token"
    export OANDA_ENV="practice"   # or "live"

Only the standard library + ``requests`` are used. ``requests`` is imported
lazily so the rest of the library has no hard dependency on it.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional

from ..models import Candle

_HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaError(RuntimeError):
    pass


class OandaClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        env: Optional[str] = None,
        *,
        timeout: float = 20.0,
    ):
        self.api_key = api_key or os.environ.get("OANDA_API_KEY")
        self.env = (env or os.environ.get("OANDA_ENV") or "practice").lower()
        if not self.api_key:
            raise OandaError(
                "No OANDA API key. Set OANDA_API_KEY or pass api_key=."
            )
        if self.env not in _HOSTS:
            raise OandaError(f"OANDA_ENV must be 'practice' or 'live', got {self.env!r}")
        self.host = _HOSTS[self.env]
        self.timeout = timeout

    def get_candles(
        self,
        instrument: str,
        granularity: str = "M15",
        count: int = 300,
        *,
        price: str = "M",
        include_incomplete: bool = False,
    ) -> List[Candle]:
        """Fetch ``count`` candles for ``instrument`` (e.g. ``EUR_USD``).

        ``granularity`` is an OANDA code: M1, M5, M15, M30, H1, H4, D, W.
        ``price`` M=mid, B=bid, A=ask.
        """
        import requests  # lazy

        url = f"{self.host}/v3/instruments/{instrument}/candles"
        params = {"granularity": granularity, "count": count, "price": price}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = requests.get(url, params=params, headers=headers,
                                timeout=self.timeout)
        except Exception as exc:  # network/proxy
            raise OandaError(f"OANDA request failed: {exc}") from exc
        if resp.status_code != 200:
            raise OandaError(f"OANDA {resp.status_code}: {resp.text[:200]}")

        out: List[Candle] = []
        for raw in resp.json().get("candles", []):
            if not raw.get("complete", False) and not include_incomplete:
                continue
            mid = raw.get("mid") or raw.get("bid") or raw.get("ask")
            ts = datetime.fromisoformat(raw["time"].replace("Z", "+00:00"))
            out.append(Candle(
                ts=ts.astimezone(timezone.utc),
                open=float(mid["o"]),
                high=float(mid["h"]),
                low=float(mid["l"]),
                close=float(mid["c"]),
                volume=float(raw.get("volume", 0)),
                complete=bool(raw.get("complete", True)),
            ))
        return out
