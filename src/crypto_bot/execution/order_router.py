from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Literal

import structlog

from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.execution.binance_errors import call_with_exchange_retry, format_exchange_error
from crypto_bot.universe import is_allowed_trading_pair

logger = structlog.get_logger(__name__)


def new_client_order_id(strategy_id: str, tag: str) -> str:
    """Binance clientOrderId max 36 chars; hex digest fits."""
    raw = f"{strategy_id}|{tag}|{time.time_ns()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"]
    amount: float
    price: float | None = None
    strategy_id: str = "default"
    tag: str = "entry"


class OrderRouter:
    """Spot orders with idempotent client order id and retries."""

    def __init__(self, client: BinanceSpotClient) -> None:
        self._ex = client.exchange

    def place(self, req: OrderRequest, *, client_order_id: str | None = None) -> dict[str, Any]:
        if not is_allowed_trading_pair(req.symbol):
            raise ValueError(f"Trading not allowed for {req.symbol}")
        cid = client_order_id or new_client_order_id(req.strategy_id, req.tag)
        params = {"newClientOrderId": cid}

        def _create() -> dict[str, Any]:
            return self._ex.create_order(
                req.symbol,
                req.type,
                req.side,
                req.amount,
                req.price,
                params,
            )

        try:
            order = call_with_exchange_retry(_create)
        except Exception as e:
            logger.exception("order_failed", client_order_id=cid, error=str(e), user_hint=format_exchange_error(e))
            raise
        logger.info("order_placed", client_order_id=cid, order_id=order.get("id"))
        return order
