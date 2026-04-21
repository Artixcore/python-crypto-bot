from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from crypto_bot.execution.order_router import OrderRequest

logger = structlog.get_logger(__name__)


@dataclass
class PaperBroker:
    """Simulated Spot fills at mid with spread and slippage (multi-symbol positions)."""

    quote_balance: float
    positions: dict[str, float] = field(default_factory=dict)
    base_position: float = 0.0  # legacy: last symbol position (use positions[symbol])
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
        sym = req.symbol
        cur = self.positions.get(sym, 0.0)
        if req.side == "buy":
            cost = notional + fee
            if cost > self.quote_balance:
                raise ValueError("insufficient_quote")
            self.quote_balance -= cost
            self.positions[sym] = cur + req.amount
            self.base_position = self.positions[sym]
        else:
            proceeds = notional - fee
            if req.amount > cur + 1e-12:
                raise ValueError("insufficient_base")
            self.positions[sym] = cur - req.amount
            self.base_position = self.positions.get(sym, 0.0)
            self.quote_balance += proceeds
        rec = {
            "id": oid,
            "symbol": req.symbol,
            "side": req.side,
            "amount": req.amount,
            "price": px,
            "fee": fee,
            "quote_balance": self.quote_balance,
            "positions": dict(self.positions),
        }
        self.orders.append(rec)
        logger.info("paper_fill", **rec)
        return rec

    def base_for(self, symbol: str) -> float:
        return float(self.positions.get(symbol, 0.0))

    def equity_usdt(self, last_by_symbol: dict[str, float]) -> float:
        t = self.quote_balance
        for sym, qty in self.positions.items():
            t += qty * float(last_by_symbol.get(sym, 0.0))
        return float(t)
