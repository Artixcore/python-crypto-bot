from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


@dataclass
class MLFilterConfig:
    min_proba: float = 0.55
    shadow: bool = False


class MLFilterModel:
    def __init__(self, pipeline: Any, config: MLFilterConfig) -> None:
        self._pipe = pipeline
        self.config = config

    def score_row(self, feats: pd.DataFrame) -> float:
        """Return P(class=1) for last row feature vector."""
        row = feats.iloc[-1:]
        proba = self._pipe.predict_proba(row[["ema_ratio", "rsi", "atr_pct"]])[:, 1]
        return float(proba[0])

    def allow(self, feats: pd.DataFrame) -> tuple[bool, float]:
        p = self.score_row(feats)
        ok = p >= self.config.min_proba
        if self.config.shadow:
            return True, p
        return ok, p


def augment_for_ml(feats: pd.DataFrame) -> pd.DataFrame:
    out = feats.copy()
    out["ema_ratio"] = out["close"] / out["ema_slow"] - 1.0
    out["atr_pct"] = out["atr"] / out["close"]
    return out


def load_ml_filter(path: Path, config: MLFilterConfig | None = None) -> MLFilterModel:
    cfg = config or MLFilterConfig()
    pipe = joblib.load(path)
    return MLFilterModel(pipe, cfg)
