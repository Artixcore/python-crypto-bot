from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import structlog

from crypto_bot.config.settings import AppSettings
from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.data.cache import KlineCache
from crypto_bot.features.indicators import add_basic_indicators

logger = structlog.get_logger(__name__)


def build_training_frame(df: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    feats = add_basic_indicators(df)
    feats["ema_ratio"] = feats["close"] / feats["ema_slow"] - 1.0
    feats["atr_pct"] = feats["atr"] / feats["close"]
    feats["future_ret"] = feats["close"].shift(-horizon) / feats["close"] - 1.0
    feats["label"] = (feats["future_ret"] > 0).astype(int)
    return feats.dropna()


def train_ml_filter_cli(args: Namespace, settings: AppSettings) -> int:
    from crypto_bot.logging_setup import configure_logging

    configure_logging()
    client = BinanceSpotClient(
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    cache = KlineCache(settings.data_dir)
    raw = cache.fetch_or_load(client, args.symbol, args.timeframe, limit=args.limit)
    frame = build_training_frame(raw)
    X = frame[["ema_ratio", "rsi", "atr_pct"]]
    y = frame["label"]
    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=200, class_weight="balanced")),
        ]
    )
    pipe.fit(X, y)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, args.out)
    preds = pipe.predict_proba(X)[:, 1]
    acc = float(np.mean((preds > 0.5) == y))
    meta = {"path": str(args.out), "rows": len(frame), "accuracy_proxy": acc}
    print(json.dumps(meta, indent=2))
    logger.info("ml_filter_trained", **meta)
    return 0
