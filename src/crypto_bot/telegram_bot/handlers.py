from __future__ import annotations

from datetime import UTC, datetime

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from crypto_bot.config.settings import AppSettings, TradingProfile
from crypto_bot.data.balances import filtered_balance
from crypto_bot.exchange_snapshot import build_snapshot
from crypto_bot.execution.binance_errors import call_with_exchange_retry, format_exchange_error
from crypto_bot.execution.order_router import OrderRequest, OrderRouter
from crypto_bot.journal.store import JournalStore
from crypto_bot.telegram_bot.auth import parse_allowed_user_ids, user_allowed
from crypto_bot.telegram_bot.formatting import (
    format_balance_table,
    format_status_slim,
    snapshot_to_messages,
)
from crypto_bot.universe import parse_pair_or_raise

logger = structlog.get_logger(__name__)


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """No Binance calls — use to verify the bot token and polling work."""
    uid = update.effective_user.id if update.effective_user else None
    logger.info("telegram_cmd_ping", user_id=uid)
    if update.effective_message:
        await update.effective_message.reply_text("pong — bot is running.")


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
            "Binance Spot bot (BTC & SOL).\n"
            "Try /ping (no API keys). Commands: /help /balance /snapshot /status /buy /sell",
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    if update.effective_message:
        await update.effective_message.reply_text(
            "/balance — BTC, SOL, USDT balances\n"
            "/snapshot — focused JSON (pairs + balances)\n"
            "/status — one-line prices + open order count\n"
            "/buy BASE USDT_AMOUNT — market buy (e.g. /buy BTC 25)\n"
            "/sell BASE QTY — market sell base (e.g. /sell SOL 0.5)\n"
            "Trading commands need CRYPTO_BOT_TELEGRAM_TRADING_ENABLED=yes and paper/live profile.",
        )


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    ex = context.application.bot_data["exchange"]
    try:
        bal = filtered_balance(ex)
        text = format_balance_table(bal)
    except Exception as e:
        text = f"Error: {format_exchange_error(e)}"
    if update.effective_message:
        await update.effective_message.reply_text(text)


async def cmd_snapshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    settings: AppSettings = context.application.bot_data["settings"]
    ex = context.application.bot_data["exchange"]
    snap = build_snapshot(ex, settings.snapshot_symbol_list())
    for part in snapshot_to_messages(snap):
        if update.effective_message:
            await update.effective_message.reply_text(part)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    settings: AppSettings = context.application.bot_data["settings"]
    ex = context.application.bot_data["exchange"]
    snap = build_snapshot(ex, settings.snapshot_symbol_list())
    if update.effective_message:
        await update.effective_message.reply_text(format_status_slim(snap))


async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    msg = update.effective_message
    if not msg:
        return
    settings: AppSettings = context.application.bot_data["settings"]
    if not settings.telegram_trading_enabled:
        await msg.reply_text("Telegram trading is disabled (set CRYPTO_BOT_TELEGRAM_TRADING_ENABLED=yes).")
        return
    args = context.args or []
    if len(args) < 2:
        await msg.reply_text("Usage: /buy BTC 25   (spend ~25 USDT)")
        return
    base = args[0].strip().upper()
    if base not in ("BTC", "SOL"):
        await msg.reply_text("BASE must be BTC or SOL")
        return
    try:
        usdt = float(args[1])
    except ValueError:
        await msg.reply_text("Invalid USDT amount")
        return
    pair = f"{base}/USDT"
    try:
        parse_pair_or_raise(pair)
    except ValueError as e:
        await msg.reply_text(str(e))
        return

    client = context.application.bot_data.get("_client")
    if client is None:
        from crypto_bot.data.binance_client import BinanceSpotClient

        client = BinanceSpotClient(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
        )
        context.application.bot_data["_client"] = client

    ex = client.exchange
    router = OrderRouter(client)

    if settings.profile != TradingProfile.LIVE or not settings.live_allowed():
        await msg.reply_text("Telegram orders require PROFILE=live, valid API keys, and LIVE_CONFIRM=yes.")
        return

    try:
        t = call_with_exchange_retry(lambda: ex.fetch_ticker(pair))
        last = float(t["last"])
        if last <= 0:
            raise ValueError("bad price")
        amount = (usdt * 0.998) / last
        order = router.place(
            OrderRequest(symbol=pair, side="buy", type="market", amount=amount, strategy_id="tg", tag="buy"),
        )
        j = JournalStore(settings.journal_path)
        j.write("telegram_buy", {"pair": pair, "usdt": usdt, "order": str(order.get("id"))})
        await msg.reply_text(f"Buy submitted id={order.get('id')} ~{amount:.8f} {base}")
    except Exception as e:
        await msg.reply_text(format_exchange_error(e))


async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    msg = update.effective_message
    if not msg:
        return
    settings: AppSettings = context.application.bot_data["settings"]
    if not settings.telegram_trading_enabled:
        await msg.reply_text("Telegram trading is disabled.")
        return
    args = context.args or []
    if len(args) < 2:
        await msg.reply_text("Usage: /sell SOL 0.5   (base asset quantity)")
        return
    base = args[0].strip().upper()
    if base not in ("BTC", "SOL"):
        await msg.reply_text("BASE must be BTC or SOL")
        return
    try:
        qty = float(args[1])
    except ValueError:
        await msg.reply_text("Invalid quantity")
        return
    pair = f"{base}/USDT"
    try:
        parse_pair_or_raise(pair)
    except ValueError as e:
        await msg.reply_text(str(e))
        return

    from crypto_bot.data.binance_client import BinanceSpotClient

    client = context.application.bot_data.get("_client")
    if client is None:
        client = BinanceSpotClient(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
        )
        context.application.bot_data["_client"] = client
    router = OrderRouter(client)

    if settings.profile != TradingProfile.LIVE or not settings.live_allowed():
        await msg.reply_text("Telegram orders require PROFILE=live, valid API keys, and LIVE_CONFIRM=yes.")
        return

    try:
        order = router.place(
            OrderRequest(symbol=pair, side="sell", type="market", amount=qty, strategy_id="tg", tag="sell"),
        )
        j = JournalStore(settings.journal_path)
        j.write("telegram_sell", {"pair": pair, "qty": qty, "order": str(order.get("id"))})
        await msg.reply_text(f"Sell submitted id={order.get('id')}")
    except Exception as e:
        await msg.reply_text(format_exchange_error(e))
