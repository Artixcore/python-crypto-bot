from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from crypto_bot.dashboard.serialize import json_safe

logger = structlog.get_logger(__name__)


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
