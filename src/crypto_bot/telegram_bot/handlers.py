from __future__ import annotations

from datetime import UTC, datetime

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from crypto_bot.config.settings import AppSettings
from crypto_bot.exchange_snapshot import build_snapshot, json_safe
from crypto_bot.telegram_bot.auth import parse_allowed_user_ids, user_allowed
from crypto_bot.telegram_bot.formatting import snapshot_to_messages

logger = structlog.get_logger(__name__)


async def _ensure_allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    settings: AppSettings = context.application.bot_data["settings"]
    allowed = parse_allowed_user_ids(settings.telegram_allowed_user_ids)
    uid = update.effective_user.id if update.effective_user else None
    msg = update.effective_message
    if not user_allowed(uid, allowed):
        logger.info("telegram_access_denied", user_id=uid, allowlist_size=len(allowed))
        if msg:
            await msg.reply_text("Unauthorized.")
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    if update.effective_message:
        await update.effective_message.reply_text(
            "Binance Spot read-only bot.\nCommands: /help /snapshot /balance",
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    if update.effective_message:
        await update.effective_message.reply_text(
            "/snapshot — full JSON snapshot (balance, tickers, orders, trades).\n"
            "/balance — wallet balances only.\n"
            "Data uses your Binance API keys from the server .env (never sent to Telegram as secrets).",
        )


async def cmd_snapshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    settings: AppSettings = context.application.bot_data["settings"]
    ex = context.application.bot_data["exchange"]
    snap = build_snapshot(ex, settings.snapshot_symbol_list())
    for part in snapshot_to_messages(snap):
        if update.effective_message:
            await update.effective_message.reply_text(part)


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    ex = context.application.bot_data["exchange"]
    try:
        subset = {
            "balance": json_safe(ex.fetch_balance()),
            "meta": {"fetched_at": datetime.now(UTC).isoformat()},
        }
    except Exception as e:
        subset = {"balance": None, "meta": {"error": str(e)}}
    for part in snapshot_to_messages(subset):
        if update.effective_message:
            await update.effective_message.reply_text(part)
