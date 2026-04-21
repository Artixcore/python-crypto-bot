from __future__ import annotations

import structlog
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from crypto_bot.config.settings import load_settings
from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.telegram_bot.handlers import (
    cmd_balance,
    cmd_buy,
    cmd_help,
    cmd_ping,
    cmd_sell,
    cmd_snapshot,
    cmd_start,
    cmd_status,
)

logger = structlog.get_logger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    logger.exception("telegram_handler_error", error=repr(err))
    if isinstance(update, Update) and update.effective_message:
        try:
            msg = f"{type(err).__name__}: {err}"
            await update.effective_message.reply_text(f"Bot error: {msg[:3500]}")
        except Exception:
            logger.exception("telegram_error_reply_failed")


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
        # Do not call load_markets() here — it can hang on dapi/network and block polling.

    app = (
        Application.builder()
        .token(token)
        .read_timeout(60.0)
        .write_timeout(60.0)
        .connect_timeout(45.0)
        .get_updates_read_timeout(60)
        .get_updates_write_timeout(60)
        .get_updates_connect_timeout(45)
        .post_init(post_init)
        .build()
    )
    app.add_error_handler(on_error)
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("snapshot", cmd_snapshot))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("sell", cmd_sell))
    return app
