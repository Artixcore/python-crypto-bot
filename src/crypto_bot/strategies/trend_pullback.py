from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from crypto_bot.strategies.base import StrategySignal


@dataclass
class TrendPullbackParams:
    """Uptrend filter + pullback to slow EMA + RSI filter + re-entry."""

    rsi_pullback_max: float = 45.0
    rsi_reentry: float = 52.0


def trend_pullback_signals(feats: pd.DataFrame, p: TrendPullbackParams | None = None) -> pd.Series:
    """
    Long when: price above trend EMA, pullback (RSI low + close below slow EMA briefly),
    then close crosses back above ema_slow with RSI confirmation.
    Simplified discrete rule set for backtesting (no lookahead: uses same-bar features only).
    """
    p = p or TrendPullbackParams()
    c = feats["close"]
    ema_s = feats["ema_slow"]
    ema_t = feats["ema_trend"]
    rsi = feats["rsi"]

    uptrend = c > ema_t
    pullback = (rsi < p.rsi_pullback_max) & (c < ema_s)
    reentry = (c > ema_s) & (rsi > p.rsi_reentry)
    raw = uptrend & pullback.shift(1).fillna(False) & reentry

    # Map to position: hold long while uptrend and not explicit exit
    exit_rule = (c < ema_t) | (rsi > 75)

    pos = pd.Series(StrategySignal.FLAT, index=feats.index, dtype="int64")
    in_long = False
    for i in range(len(feats)):
        if not in_long and bool(raw.iloc[i]):
            in_long = True
        elif in_long and bool(exit_rule.iloc[i]):
            in_long = False
        pos.iloc[i] = StrategySignal.LONG if in_long else StrategySignal.FLAT

    return pos
