from __future__ import annotations

import structlog
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from crypto_bot.config.settings import AppSettings, TradingProfile
from crypto_bot.data.balances import filtered_balance
from crypto_bot.data.binance_client import BinanceSpotClient
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
from crypto_bot.telegram_bot.keyboards import (
    hub_keyboard,
    parse_menu_callback,
    subview_keyboard,
)
from crypto_bot.telegram_bot.views import (
    build_indicator_lines,
    format_account_html,
    format_execution_log_html,
    format_help_html,
    format_hub_html,
    format_markets_html,
    format_orders_and_fills_html,
    format_signals_html,
    format_strategy_risk_html,
    format_trade_help_html,
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
    if user_allowed(uid, allowed):
        return True
    logger.info("telegram_access_denied", user_id=uid, allowlist_size=len(allowed))
    if update.callback_query:
        await update.callback_query.answer("Unauthorized.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("Unauthorized.")
    return False


def _spot_client(context: ContextTypes.DEFAULT_TYPE) -> BinanceSpotClient:
    client = context.application.bot_data.get("_client")
    if client is not None:
        return client
    settings: AppSettings = context.application.bot_data["settings"]
    client = BinanceSpotClient(
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    context.application.bot_data["_client"] = client
    return client


async def _reply_or_edit_hub(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup,
) -> None:
    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
            return
        except TelegramError as e:
            logger.warning("telegram_edit_failed", error=str(e))
            await update.callback_query.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
            return
    if update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )


async def on_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    q = update.callback_query
    if not q:
        return
    await q.answer()
    view_id = parse_menu_callback(q.data)
    if not view_id:
        return

    settings: AppSettings = context.application.bot_data["settings"]
    ex = context.application.bot_data["exchange"]
    client = _spot_client(context)
    journal = JournalStore(settings.journal_path)
    snap = build_snapshot(ex, settings.snapshot_symbol_list())

    if view_id == "hub":
        text = format_hub_html(settings, snap)
        markup = hub_keyboard()
    elif view_id == "acct":
        text = format_account_html(settings, snap)
        markup = subview_keyboard()
    elif view_id == "mkt":
        text = format_markets_html(snap)
        markup = subview_keyboard()
    elif view_id == "ord":
        text = format_orders_and_fills_html(snap)
        markup = subview_keyboard()
    elif view_id == "strat":
        text = format_strategy_risk_html(settings, journal)
        markup = subview_keyboard()
    elif view_id == "log":
        text = format_execution_log_html(journal)
        markup = subview_keyboard()
    elif view_id == "sig":
        ind = build_indicator_lines(client, settings)
        text = format_signals_html(settings, journal, ind)
        markup = subview_keyboard()
    elif view_id == "trd":
        text = format_trade_help_html(settings)
        markup = subview_keyboard()
    elif view_id == "hlp":
        text = format_help_html()
        markup = subview_keyboard()
    else:
        text = format_hub_html(settings, snap)
        markup = hub_keyboard()

    await _reply_or_edit_hub(update, context, text, markup)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    settings: AppSettings = context.application.bot_data["settings"]
    ex = context.application.bot_data["exchange"]
    snap = build_snapshot(ex, settings.snapshot_symbol_list())
    text = format_hub_html(settings, snap)
    await _reply_or_edit_hub(update, context, text, hub_keyboard())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_allowed(update, context):
        return
    text = format_help_html()
    await _reply_or_edit_hub(update, context, text, subview_keyboard())


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
