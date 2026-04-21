from __future__ import annotations

import json
from argparse import Namespace

import structlog

from crypto_bot.backtest.engine import BacktestConfig, run_backtest
from crypto_bot.config.settings import AppSettings
from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.data.cache import KlineCache

logger = structlog.get_logger(__name__)


def run_backtest_cli(args: Namespace, settings: AppSettings) -> int:
    from crypto_bot.logging_setup import configure_logging

    configure_logging()
    client = BinanceSpotClient(
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    cache = KlineCache(settings.data_dir)
    df = cache.fetch_or_load(client, args.symbol, args.timeframe, limit=args.limit)
    cfg = BacktestConfig()
    result = run_backtest(df, config=cfg)
    print(json.dumps(result.metrics, indent=2))
    if not result.trades.empty:
        print(result.trades.tail(5).to_string(index=False))
    logger.info("backtest_done", metrics=result.metrics)
    return 0
