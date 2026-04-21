from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import structlog

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


def build_snapshot(exchange: Any, symbols: list[str]) -> dict[str, Any]:
    """
    Aggregate read-only Spot data from ccxt. Best-effort: partial results + errors list.
    """
    errors: list[str] = []
    out: dict[str, Any] = {
        "balance": None,
        "tickers": {},
        "open_orders": None,
        "my_trades": {},
        "exchange_time_ms": None,
        "exchange_status": None,
    }

    try:
        out["balance"] = json_safe(exchange.fetch_balance())
    except Exception as e:
        msg = f"fetch_balance: {e}"
        logger.warning("snapshot_balance", error=str(e))
        errors.append(msg)

    for sym in symbols:
        try:
            out["tickers"][sym] = json_safe(exchange.fetch_ticker(sym))
        except Exception as e:
            errors.append(f"fetch_ticker {sym}: {e}")

    try:
        out["open_orders"] = json_safe(exchange.fetch_open_orders())
    except Exception as e:
        errors.append(f"fetch_open_orders: {e}")

    for sym in symbols[:3]:
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
