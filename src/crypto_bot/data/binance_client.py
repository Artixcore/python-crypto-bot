from __future__ import annotations

import time
from typing import Any

import ccxt

from crypto_bot.data.spot_public import fetch_klines_spot


class BinanceSpotClient:
    """Read-focused Binance Spot wrapper (ccxt). Trading methods used only by execution layer."""

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        *,
        enable_rate_limit: bool = True,
        timeout_ms: int = 30_000,
    ) -> None:
        opts: dict[str, Any] = {
            "apiKey": api_key or None,
            "secret": api_secret or None,
            "enableRateLimit": enable_rate_limit,
            "timeout": timeout_ms,
            "options": {"defaultType": "spot"},
        }
        self._exchange = ccxt.binance(opts)

    @property
    def exchange(self) -> ccxt.binance:
        return self._exchange

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since_ms: int | None = None,
        limit: int | None = None,
    ) -> list[list[float]]:
        """Fetch OHLCV via public Spot REST (no delivery/futures market discovery)."""
        lim = limit if limit is not None else 500
        return fetch_klines_spot(symbol, timeframe, limit=lim, start_time_ms=since_ms)

    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        return self._exchange.fetch_ticker(symbol)

    def load_markets(self) -> dict[str, Any]:
        return self._exchange.load_markets()

    def sleep_for_rate_limit(self) -> None:
        """Honor ccxt throttle if needed."""
        time.sleep(self._exchange.rateLimit / 1000.0 if self._exchange.rateLimit else 0)
