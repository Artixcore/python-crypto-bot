from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from crypto_bot.config.settings import AppSettings, TradingProfile
from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.data.cache import KlineCache
from crypto_bot.logging_setup import configure_logging


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crypto_bot", description="Binance Spot trading agent CLI")
    p.add_argument("--profile", choices=[e.value for e in TradingProfile], default=None)
    sub = p.add_subparsers(dest="command", required=True)

    fk = sub.add_parser("fetch-klines", help="Download and cache OHLCV (read-only)")
    fk.add_argument("--symbol", default="BTC/USDT")
    fk.add_argument("--timeframe", default="1h")
    fk.add_argument("--limit", type=int, default=500)
    fk.add_argument("--force", action="store_true")

    bt = sub.add_parser("backtest", help="Run backtest (see backtest module)")
    bt.add_argument("--symbol", default="BTC/USDT")
    bt.add_argument("--timeframe", default="1h")
    bt.add_argument("--limit", type=int, default=2000)

    wf = sub.add_parser("walk-forward", help="Walk-forward / OOS evaluation")
    wf.add_argument("--symbol", default="BTC/USDT")
    wf.add_argument("--timeframe", default="1h")
    wf.add_argument("--limit", type=int, default=5000)
    wf.add_argument("--train-bars", type=int, default=400)
    wf.add_argument("--test-bars", type=int, default=100)
    wf.add_argument("--step-bars", type=int, default=100)

    run = sub.add_parser("run", help="Paper or live runner loop")
    run.add_argument("--symbol", default="BTC/USDT")
    run.add_argument("--timeframe", default="1h")
    run.add_argument("--interval-sec", type=int, default=60)

    train = sub.add_parser("train-ml-filter", help="Train optional ML filter from cached features")
    train.add_argument("--symbol", default="BTC/USDT")
    train.add_argument("--timeframe", default="1h")
    train.add_argument("--limit", type=int, default=2000)
    train.add_argument("--out", type=Path, default=Path("models/ml_filter.joblib"))

    return p


def cmd_fetch_klines(args: argparse.Namespace, settings: AppSettings) -> int:
    configure_logging()
    client = BinanceSpotClient(
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    cache = KlineCache(settings.data_dir)
    df = cache.fetch_or_load(
        client,
        args.symbol,
        args.timeframe,
        limit=args.limit,
        force_refresh=args.force,
    )
    print(f"rows={len(df)} path={cache.path_for(args.symbol, args.timeframe, args.limit, None)}")
    print(df.tail(3).to_string(index=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = AppSettings()
    if args.profile:
        settings = AppSettings(profile=TradingProfile(args.profile))

    if args.command == "fetch-klines":
        return cmd_fetch_klines(args, settings)

    if args.command == "backtest":
        from crypto_bot.backtest.runner import run_backtest_cli

        return run_backtest_cli(args, settings)

    if args.command == "walk-forward":
        from crypto_bot.backtest.walk_forward import run_walk_forward_cli

        return run_walk_forward_cli(args, settings)

    if args.command == "run":
        from crypto_bot.live.runner import run_loop

        return asyncio.run(run_loop(args, settings))

    if args.command == "train-ml-filter":
        from crypto_bot.ml.train import train_ml_filter_cli

        return train_ml_filter_cli(args, settings)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
