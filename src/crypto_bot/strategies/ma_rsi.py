from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from crypto_bot.strategies.base import StrategySignal


@dataclass
class MaRsiParams:
    rsi_buy_max: float = 45.0
    rsi_exit_min: float = 70.0


def ma_rsi_signals(feats: pd.DataFrame, p: MaRsiParams | None = None) -> pd.Series:
    """
    Long on bullish MA crossover when RSI is not overbought.
    Exit on bearish cross or RSI overbought.
    """
    p = p or MaRsiParams()
    mf = feats["ma_fast"]
    ms = feats["ma_slow"]
    rsi = feats["rsi"]

    cross_up = (mf > ms) & (mf.shift(1) <= ms.shift(1))
    cross_dn = (mf < ms) & (mf.shift(1) >= ms.shift(1))
    entry = cross_up & (rsi < p.rsi_buy_max)
    exit_rule = cross_dn | (rsi > p.rsi_exit_min)

    pos = pd.Series(StrategySignal.FLAT, index=feats.index, dtype="int64")
    in_long = False
    for i in range(len(feats)):
        if not in_long and bool(entry.iloc[i]):
            in_long = True
        elif in_long and bool(exit_rule.iloc[i]):
            in_long = False
        pos.iloc[i] = StrategySignal.LONG if in_long else StrategySignal.FLAT

    return pos
