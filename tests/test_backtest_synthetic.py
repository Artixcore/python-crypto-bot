import numpy as np
import pandas as pd

from crypto_bot.backtest.engine import BacktestConfig, run_backtest


def test_backtest_runs_on_synthetic_uptrend():
    n = 300
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    t = np.linspace(0, 5, n)
    close = 100 + np.cumsum(np.random.default_rng(42).normal(0.02, 0.5, n))
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "open": close * 0.999,
            "high": close * 1.002,
            "low": close * 0.998,
            "close": close,
            "volume": np.full(n, 1000.0),
        }
    )
    res = run_backtest(df, config=BacktestConfig(initial_equity=10_000.0))
    assert len(res.equity_curve) > 0
    assert "max_dd_pct" in res.metrics
