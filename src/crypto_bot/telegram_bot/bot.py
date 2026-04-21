from __future__ import annotations

import structlog
from telegram.ext import Application, CommandHandler

from crypto_bot.config.settings import load_settings
from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.telegram_bot.handlers import (
    cmd_balance,
    cmd_buy,
    cmd_help,
    cmd_sell,
    cmd_snapshot,
    cmd_start,
    cmd_status,
)

logger = structlog.get_logger(__name__)


def build_application() -> Application:
    settings = load_settings()
    token = settings.telegram_bot_token.strip()
    if not token:
        raise SystemExit(
            "Missing CRYPTO_BOT_TELEGRAM_BOT_TOKEN. Add it to .env (from BotFather).",
        )

    async def post_init(application: Application) -> None:
        application.bot_data["settings"] = settings
        client = BinanceSpotClient(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
        )
        application.bot_data["exchange"] = client.exchange
        application.bot_data["_client"] = client
        logger.info("telegram_loading_markets")
        try:
            application.bot_data["exchange"].load_markets()
        except Exception as e:
            logger.warning("telegram_load_markets_failed", error=str(e))

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("snapshot", cmd_snapshot))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("sell", cmd_sell))
    return app
