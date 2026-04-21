from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import structlog

from crypto_bot.data.balances import filtered_balance
from crypto_bot.universe import TRADING_PAIRS, is_allowed_trading_pair

logger = structlog.get_logger(__name__)


def json_safe(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [json_safe(x) for x in obj]
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        try:
            return json_safe(vars(obj))
        except TypeError:
            pass
    return str(obj)


def _filter_open_orders(orders: list[dict] | None) -> list[dict]:
    if not orders:
        return []
    allowed = set(TRADING_PAIRS)
    return [o for o in orders if str(o.get("symbol", "")).replace(" ", "") in allowed]


def build_snapshot(exchange: Any, symbols: list[str]) -> dict[str, Any]:
    """
    Read-only Spot snapshot restricted to TRADING_PAIRS (tickers, trades, open orders).
    Balance is BTC/SOL/USDT only.
    """
    errors: list[str] = []
    sym_list = [s for s in symbols if is_allowed_trading_pair(s)]
    if not sym_list:
        sym_list = list(TRADING_PAIRS)

    out: dict[str, Any] = {
        "balance": None,
        "tickers": {},
        "open_orders": None,
        "my_trades": {},
        "exchange_time_ms": None,
        "exchange_status": None,
    }

    try:
        out["balance"] = filtered_balance(exchange)
    except Exception as e:
        msg = f"fetch_balance: {e}"
        logger.warning("snapshot_balance", error=str(e))
        errors.append(msg)

    for sym in sym_list:
        try:
            out["tickers"][sym] = json_safe(exchange.fetch_ticker(sym))
        except Exception as e:
            errors.append(f"fetch_ticker {sym}: {e}")

    try:
        raw_orders = exchange.fetch_open_orders()
        out["open_orders"] = json_safe(_filter_open_orders(raw_orders))
    except Exception as e:
        errors.append(f"fetch_open_orders: {e}")

    for sym in sym_list:
        try:
            out["my_trades"][sym] = json_safe(
                exchange.fetch_my_trades(sym, limit=25),
            )
        except Exception as e:
            errors.append(f"fetch_my_trades {sym}: {e}")

    try:
        out["exchange_time_ms"] = exchange.fetch_time()
    except Exception as e:
        errors.append(f"fetch_time: {e}")

    has = getattr(exchange, "has", None) or {}
    if isinstance(has, dict) and has.get("fetchStatus"):
        try:
            out["exchange_status"] = json_safe(exchange.fetch_status())
        except Exception as e:
            errors.append(f"fetch_status: {e}")

    meta = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "errors": errors,
        "error": "; ".join(errors) if errors else None,
    }
    out["meta"] = meta
    return out
