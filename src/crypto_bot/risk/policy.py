from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class StopTakePolicy:
    atr_stop_mult: float = 2.0
    take_profit_r: float = 2.0
    trail_after_r: float = 1.0
    trail_atr_mult: float = 1.5


@dataclass
class ExitPlan:
    stop_price: float
    take_profit_price: float
    trail_active: bool = False
    trail_stop: float | None = None


def initial_plan_for_long(
    entry: float,
    atr: float,
    policy: StopTakePolicy,
) -> ExitPlan:
    stop = entry - policy.atr_stop_mult * atr
    risk = entry - stop
    tp = entry + policy.take_profit_r * risk
    return ExitPlan(stop_price=stop, take_profit_price=tp)


def update_trailing_long(
    high_since_entry: float,
    plan: ExitPlan,
    atr: float,
    policy: StopTakePolicy,
    entry: float,
) -> ExitPlan:
    risk = entry - plan.stop_price
    if risk <= 0:
        return plan
    mfe_r = (high_since_entry - entry) / risk
    if mfe_r < policy.trail_after_r:
        return plan
    trail = high_since_entry - policy.trail_atr_mult * atr
    trail_stop = max(plan.stop_price, trail)
    return ExitPlan(
        stop_price=trail_stop,
        take_profit_price=plan.take_profit_price,
        trail_active=True,
        trail_stop=trail_stop,
    )


def check_exit_long(
    low: float,
    high: float,
    close: float,
    plan: ExitPlan,
) -> tuple[bool, float, str]:
    """Returns (exit?, exit_price, reason)."""
    if low <= plan.stop_price:
        return True, float(plan.stop_price), "stop"
    if high >= plan.take_profit_price:
        return True, float(plan.take_profit_price), "take_profit"
    return False, float(close), ""
