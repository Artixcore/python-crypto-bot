import numpy as np
import pandas as pd

from crypto_bot.features.indicators import add_ma_rsi_indicators
from crypto_bot.strategies.ma_rsi import MaRsiParams, ma_rsi_signals


def test_ma_rsi_produces_series():
    n = 80
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    df = pd.DataFrame(
        {
            "open": close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "volume": np.full(n, 100.0),
        },
        index=idx,
    )
    feats = add_ma_rsi_indicators(df, ma_fast=5, ma_slow=10, rsi_period=7).dropna()
    sig = ma_rsi_signals(feats, MaRsiParams())
    assert len(sig) == len(feats)
    assert sig.iloc[-1] in (0, 1)
