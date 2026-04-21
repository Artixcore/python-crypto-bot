from crypto_bot.risk.policy import (
    StopTakePolicy,
    check_exit_long,
    initial_plan_for_long,
)
from crypto_bot.risk.position_sizing import risk_based_size


def test_initial_plan_long():
    p = StopTakePolicy(atr_stop_mult=2.0, take_profit_r=2.0)
    plan = initial_plan_for_long(100.0, 1.0, p)
    assert plan.stop_price == 98.0
    assert plan.take_profit_price == 104.0


def test_check_exit_stop():
    p = StopTakePolicy()
    plan = initial_plan_for_long(100.0, 1.0, p)
    hit, px, reason = check_exit_long(97.0, 101.0, 99.0, plan)
    assert hit and reason == "stop"


def test_risk_based_size():
    q = risk_based_size(10_000.0, 100.0, 98.0, 0.01)
    assert q > 0


def test_governor_kill_switch():
    from crypto_bot.risk.governor import RiskDecision, RiskGovernor

    g = RiskGovernor(kill_switch=True)
    d, _ = g.pre_trade(10_000.0, 100.0, 0)
    assert d == RiskDecision.HALT
