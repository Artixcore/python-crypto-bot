"""Public Spot REST (no market metadata load) — avoids ccxt multi-market discovery."""

from __future__ import annotations

import httpx

_SPOT_KLINES = "https://api.binance.com/api/v3/klines"


def fetch_klines_spot(
    symbol: str,
    interval: str,
    *,
    limit: int = 500,
    start_time_ms: int | None = None,
    timeout: float = 60.0,
) -> list[list[float]]:
    """
    Returns OHLCV rows: [open_time_ms, open, high, low, close, volume].
    symbol: CCXT style 'BTC/USDT' -> BTCUSDT.
    """
    sym = symbol.replace("/", "")
    params: dict[str, int | str] = {"symbol": sym, "interval": interval, "limit": limit}
    if start_time_ms is not None:
        params["startTime"] = start_time_ms
    with httpx.Client(timeout=timeout) as client:
        r = client.get(_SPOT_KLINES, params=params)
        r.raise_for_status()
        raw = r.json()
    out: list[list[float]] = []
    for row in raw:
        out.append(
            [
                float(row[0]),
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
            ]
        )
    return out
