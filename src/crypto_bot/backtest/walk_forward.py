from __future__ import annotations

import json
from argparse import Namespace

import pandas as pd
import structlog

from crypto_bot.backtest.engine import BacktestConfig, run_backtest
from crypto_bot.config.settings import AppSettings
from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.data.cache import KlineCache

logger = structlog.get_logger(__name__)


def run_walk_forward_cli(args: Namespace, settings: AppSettings) -> int:
    from crypto_bot.logging_setup import configure_logging

    configure_logging()
    client = BinanceSpotClient(
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    cache = KlineCache(settings.data_dir)
    total = args.train_bars + args.test_bars + 200
    df = cache.fetch_or_load(client, args.symbol, args.timeframe, limit=max(args.limit, total))
    cfg = BacktestConfig()

    folds: list[dict[str, float | int]] = []
    start = 0
    fold_idx = 0
    while start + args.train_bars + args.test_bars <= len(df):
        oos = df.iloc[start + args.train_bars : start + args.train_bars + args.test_bars].copy()
        res = run_backtest(oos, config=cfg)
        row = dict(res.metrics)
        row["fold"] = fold_idx
        row["oos_start"] = int(start + args.train_bars)
        folds.append(row)
        fold_idx += 1
        start += args.step_bars

    summary = pd.DataFrame(folds)
    print(summary.to_string(index=False))
    agg = {
        "mean_cagr_pct": float(summary["cagr_pct"].mean()) if len(summary) else 0.0,
        "mean_max_dd_pct": float(summary["max_dd_pct"].mean()) if len(summary) else 0.0,
        "mean_profit_factor": float(summary["profit_factor"].mean()) if len(summary) else 0.0,
        "folds": len(summary),
    }
    print(json.dumps(agg, indent=2))
    logger.info("walk_forward_done", **agg)
    return 0
