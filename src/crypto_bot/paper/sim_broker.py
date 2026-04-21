from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from crypto_bot.execution.order_router import OrderRequest

logger = structlog.get_logger(__name__)


@dataclass
class PaperBroker:
    """Simulated Spot fills at mid with spread and slippage."""

    quote_balance: float
    base_position: float = 0.0
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    spread_bps: float = 5.0
    last_price: float = 0.0
    orders: list[dict[str, object]] = field(default_factory=list)

    def _adjust_price(self, price: float, side: str) -> float:
        half_spread = (self.spread_bps / 10_000.0) * price / 2
        slip = (self.slippage_bps / 10_000.0) * price
        if side == "buy":
            return price + half_spread + slip
        return price - half_spread - slip

    def _fee(self, notional: float) -> float:
        return notional * (self.fee_bps / 10_000.0)

    def market(self, req: OrderRequest, mid_price: float) -> dict[str, object]:
        self.last_price = mid_price
        px = self._adjust_price(mid_price, req.side)
        notional = px * req.amount
        fee = self._fee(notional)
        oid = len(self.orders) + 1
        if req.side == "buy":
            cost = notional + fee
            if cost > self.quote_balance:
                raise ValueError("insufficient_quote")
            self.quote_balance -= cost
            self.base_position += req.amount
        else:
            proceeds = notional - fee
            if req.amount > self.base_position + 1e-12:
                raise ValueError("insufficient_base")
            self.base_position -= req.amount
            self.quote_balance += proceeds
        rec = {
            "id": oid,
            "symbol": req.symbol,
            "side": req.side,
            "amount": req.amount,
            "price": px,
            "fee": fee,
            "quote_balance": self.quote_balance,
            "base_position": self.base_position,
        }
        self.orders.append(rec)
        logger.info("paper_fill", **rec)
        return rec
