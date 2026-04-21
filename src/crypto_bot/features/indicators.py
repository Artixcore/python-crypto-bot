from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def add_basic_indicators(
    df: pd.DataFrame,
    *,
    ema_fast: int = 21,
    ema_slow: int = 55,
    ema_trend: int = 200,
    atr_period: int = 14,
    rsi_period: int = 14,
) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = ema(out["close"], ema_fast)
    out["ema_slow"] = ema(out["close"], ema_slow)
    out["ema_trend"] = ema(out["close"], ema_trend)
    out["atr"] = atr(out, atr_period)
    out["rsi"] = rsi(out["close"], rsi_period)
    return out


def add_ma_rsi_indicators(
    df: pd.DataFrame,
    *,
    ma_fast: int = 12,
    ma_slow: int = 26,
    rsi_period: int = 14,
    atr_period: int = 14,
) -> pd.DataFrame:
    out = df.copy()
    out["ma_fast"] = sma(out["close"], ma_fast)
    out["ma_slow"] = sma(out["close"], ma_slow)
    out["rsi"] = rsi(out["close"], rsi_period)
    out["atr"] = atr(out, atr_period)
    return out
