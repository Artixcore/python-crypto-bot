from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol

import pandas as pd


class StrategySignal(IntEnum):
    FLAT = 0
    LONG = 1


@dataclass
class StrategyMeta:
    strategy_id: str
    version: str


class Strategy(Protocol):
    meta: StrategyMeta

    def signals(self, feats: pd.DataFrame) -> pd.Series:
        """Aligned with feats index; StrategySignal per row. No lookahead beyond row i."""
