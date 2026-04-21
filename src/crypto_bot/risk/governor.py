from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class RiskDecision(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"
    HALT = "halt"


@dataclass
class RiskLimits:
    max_open_positions: int = 2
    max_daily_loss_pct: float = 3.0
    max_orders_per_day: int = 50
    max_position_notional_pct: float = 25.0


@dataclass
class RiskGovernor:
    limits: RiskLimits = field(default_factory=RiskLimits)
    kill_switch: bool = False
    day_start_equity: float | None = None
    orders_today: int = 0
    current_day: str | None = None
    realized_pnl_today: float = 0.0

    def _roll_day(self, equity: float) -> None:
        today = datetime.now(UTC).date().isoformat()
        if self.current_day != today:
            self.current_day = today
            self.orders_today = 0
            self.day_start_equity = equity
            self.realized_pnl_today = 0.0

    def register_fill_pnl(self, pnl: float) -> None:
        self.realized_pnl_today += pnl

    def pre_trade(
        self,
        equity: float,
        proposed_notional: float,
        open_positions: int,
    ) -> tuple[RiskDecision, str]:
        if self.kill_switch:
            return RiskDecision.HALT, "kill_switch"

        self._roll_day(equity)
        assert self.day_start_equity is not None

        if self.day_start_equity and self.day_start_equity > 0:
            loss_pct = max(0.0, -self.realized_pnl_today / self.day_start_equity * 100.0)
            if loss_pct >= self.limits.max_daily_loss_pct:
                logger.warning("daily_loss_limit", loss_pct=loss_pct)
                return RiskDecision.HALT, "daily_loss_limit"

        if open_positions >= self.limits.max_open_positions:
            return RiskDecision.REJECT, "max_open_positions"

        if equity > 0 and (proposed_notional / equity) * 100 > self.limits.max_position_notional_pct:
            return RiskDecision.REJECT, "max_notional_pct"

        if self.orders_today >= self.limits.max_orders_per_day:
            return RiskDecision.REJECT, "max_orders_per_day"

        return RiskDecision.ALLOW, "ok"

    def on_order_submitted(self) -> None:
        self.orders_today += 1
