from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Callback data: "v:<id>" — keep short (Telegram limit 64 bytes per button).

CB_HUB = "v:hub"
CB_ACCOUNT = "v:acct"
CB_MARKETS = "v:mkt"
CB_ORDERS = "v:ord"
CB_STRATEGY = "v:strat"
CB_LOGS = "v:log"
CB_SIGNALS = "v:sig"
CB_TRADE = "v:trd"
CB_HELP = "v:hlp"


def parse_menu_callback(data: str | None) -> str | None:
    """Return view id after 'v:' or None."""
    if not data or not data.startswith("v:"):
        return None
    return data[2:]


def hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Account", callback_data=CB_ACCOUNT),
                InlineKeyboardButton("Markets", callback_data=CB_MARKETS),
            ],
            [
                InlineKeyboardButton("Orders & fills", callback_data=CB_ORDERS),
                InlineKeyboardButton("Strategy & risk", callback_data=CB_STRATEGY),
            ],
            [
                InlineKeyboardButton("Live signals", callback_data=CB_SIGNALS),
                InlineKeyboardButton("Execution log", callback_data=CB_LOGS),
            ],
            [
                InlineKeyboardButton("Trade", callback_data=CB_TRADE),
                InlineKeyboardButton("Help", callback_data=CB_HELP),
            ],
            [InlineKeyboardButton("Refresh", callback_data=CB_HUB)],
        ],
    )


def subview_keyboard() -> InlineKeyboardMarkup:
    """Back navigation from any sub-view to hub."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Main menu", callback_data=CB_HUB)],
        ],
    )
