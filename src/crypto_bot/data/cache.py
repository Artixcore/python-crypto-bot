from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from crypto_bot.data.binance_client import BinanceSpotClient


def _cache_key(symbol: str, timeframe: str, limit: int | None, since_ms: int | None) -> str:
    raw = f"{symbol}|{timeframe}|{limit}|{since_ms}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class KlineCache:
    """Parquet cache for OHLCV under data_dir."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, symbol: str, timeframe: str, limit: int | None, since_ms: int | None) -> Path:
        safe = symbol.replace("/", "_")
        key = _cache_key(symbol, timeframe, limit, since_ms)
        return self._dir / f"klines_{safe}_{timeframe}_{key}.parquet"

    def read(self, path: Path) -> pd.DataFrame | None:
        if not path.exists():
            return None
        return pd.read_parquet(path)

    def write(self, path: Path, df: pd.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    def fetch_or_load(
        self,
        client: BinanceSpotClient,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        since_ms: int | None = None,
        *,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        path = self.path_for(symbol, timeframe, limit, since_ms)
        if not force_refresh:
            existing = self.read(path)
            if existing is not None and not existing.empty:
                return existing

        raw = client.fetch_ohlcv(symbol, timeframe, since_ms=since_ms, limit=limit)
        df = pd.DataFrame(
            raw,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        self.write(path, df)
        return df
