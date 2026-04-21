from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from crypto_bot.features.indicators import add_ma_rsi_indicators
from crypto_bot.risk.policy import (
    StopTakePolicy,
    check_exit_long,
    initial_plan_for_long,
    update_trailing_long,
)
from crypto_bot.risk.position_sizing import fixed_pct_of_equity_size
from crypto_bot.strategies.base import StrategySignal
from crypto_bot.strategies.ma_rsi import MaRsiParams, ma_rsi_signals


@dataclass(frozen=True)
class BacktestConfig:
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    initial_equity: float = 10_000.0
    position_pct: float = 2.0
    ma_fast_period: int = 12
    ma_slow_period: int = 26
    rsi_period: int = 14
    ma_rsi_params: MaRsiParams = field(default_factory=MaRsiParams)
    stop_take: StopTakePolicy = field(default_factory=StopTakePolicy)


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: pd.DataFrame
    metrics: dict[str, float]


def _apply_costs(price: float, *, side: str, fee_bps: float, slip_bps: float) -> float:
    slip = slip_bps / 10_000.0
    fee = fee_bps / 10_000.0
    if side == "buy":
        return price * (1 + slip) * (1 + fee)
    return price * (1 - slip) * (1 - fee)


def run_backtest(
    ohlcv: pd.DataFrame,
    *,
    config: BacktestConfig | None = None,
    signals: pd.Series | None = None,
) -> BacktestResult:
    """
    Bar simulation: signal evaluated on bar i (features up to i), entries/exits on bar i+1 open
    unless stopped intrabar (uses low/high).
    """
    cfg = config or BacktestConfig()
    feats = add_ma_rsi_indicators(
        ohlcv,
        ma_fast=cfg.ma_fast_period,
        ma_slow=cfg.ma_slow_period,
        rsi_period=cfg.rsi_period,
    )
    feats = feats.dropna().copy()
    if signals is None:
        sig = ma_rsi_signals(feats, cfg.ma_rsi_params)
    else:
        sig = signals.reindex(feats.index).fillna(StrategySignal.FLAT)

    equity = cfg.initial_equity
    cash = equity
    position_qty = 0.0
    entry_price = 0.0
    plan = None
    high_since_entry = 0.0
    entry_time = feats.index[0]

    equity_hist: list[float] = []
    trade_rows: list[dict[str, object]] = []

    opens = feats["open"].to_numpy()
    highs = feats["high"].to_numpy()
    lows_arr = feats["low"].to_numpy()
    closes = feats["close"].to_numpy()
    atrs = feats["atr"].to_numpy()
    times = feats.index

    want_long = sig.to_numpy() == StrategySignal.LONG

    for i in range(len(feats) - 1):
        ts = times[i]
        ts_next = times[i + 1]
        o_next = float(opens[i + 1])
        h = float(highs[i + 1])
        l = float(lows_arr[i + 1])
        c = float(closes[i + 1])
        atr = float(atrs[i + 1])

        if position_qty > 0 and plan is not None:
            high_since_entry = max(high_since_entry, h)
            plan = update_trailing_long(high_since_entry, plan, atr, cfg.stop_take, entry_price)
            exit_hit, exit_px, reason = check_exit_long(l, h, c, plan)
            if exit_hit:
                proceeds = position_qty * _apply_costs(
                    exit_px, side="sell", fee_bps=cfg.fee_bps, slip_bps=cfg.slippage_bps
                )
                pnl = proceeds - position_qty * entry_price
                cash += proceeds
                trade_rows.append(
                    {
                        "exit_time": ts_next,
                        "entry_time": entry_time,
                        "side": "long",
                        "qty": position_qty,
                        "entry": entry_price,
                        "exit": exit_px,
                        "pnl": pnl,
                        "reason": reason,
                    }
                )
                position_qty = 0.0
                plan = None

        target_long = bool(want_long[i])
        if position_qty == 0 and target_long:
            stop_px = o_next - cfg.stop_take.atr_stop_mult * atr
            if stop_px > 0 and stop_px < o_next:
                qty = fixed_pct_of_equity_size(cash, o_next, cfg.position_pct)
                cost = (
                    qty
                    * _apply_costs(
                        o_next, side="buy", fee_bps=cfg.fee_bps, slip_bps=cfg.slippage_bps
                    )
                )
                if qty > 0 and cost <= cash:
                    cash -= cost
                    position_qty = qty
                    entry_price = cost / qty
                    entry_time = ts_next
                    high_since_entry = h
                    plan = initial_plan_for_long(entry_price, atr, cfg.stop_take)
                    plan = update_trailing_long(
                        high_since_entry, plan, atr, cfg.stop_take, entry_price
                    )

        if position_qty > 0 and not target_long:
            exit_px = _apply_costs(
                o_next, side="sell", fee_bps=cfg.fee_bps, slip_bps=cfg.slippage_bps
            )
            proceeds = position_qty * exit_px
            pnl = proceeds - position_qty * entry_price
            cash += proceeds
            trade_rows.append(
                {
                    "exit_time": ts_next,
                    "entry_time": entry_time,
                    "side": "long",
                    "qty": position_qty,
                    "entry": entry_price,
                    "exit": exit_px,
                    "pnl": pnl,
                    "reason": "signal_flat",
                }
            )
            position_qty = 0.0
            plan = None

        mark = cash + position_qty * c
        equity_hist.append(mark)

    equity_curve = pd.Series(equity_hist, index=times[1 : len(equity_hist) + 1])
    trades = pd.DataFrame(trade_rows)
    metrics = _compute_metrics(equity_curve, trades, cfg.initial_equity)
    return BacktestResult(equity_curve=equity_curve, trades=trades, metrics=metrics)


def _compute_metrics(equity: pd.Series, trades: pd.DataFrame, initial: float) -> dict[str, float]:
    if equity.empty:
        return {
            "cagr_pct": 0.0,
            "max_dd_pct": 0.0,
            "sharpe": 0.0,
            "profit_factor": 0.0,
            "n_trades": 0.0,
        }

    ret = equity.pct_change().fillna(0.0)
    vol = float(ret.std()) if len(ret) > 1 else 0.0
    sharpe = (float(ret.mean()) / vol * np.sqrt(365 * 24)) if vol > 0 else 0.0

    peak = equity.cummax()
    dd = (equity - peak) / peak
    max_dd_pct = float(dd.min() * 100)

    years = max(len(equity) / (365 * 24), 1e-9)
    total_ret = float(equity.iloc[-1] / initial - 1.0)
    cagr = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0.0
    cagr_pct = float(cagr * 100)

    gross_profit = float(trades.loc[trades["pnl"] > 0, "pnl"].sum()) if len(trades) else 0.0
    gross_loss = float(-trades.loc[trades["pnl"] < 0, "pnl"].sum()) if len(trades) else 0.0
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    return {
        "cagr_pct": cagr_pct,
        "max_dd_pct": max_dd_pct,
        "sharpe": float(sharpe),
        "profit_factor": float(pf) if pf != float("inf") else 99.0,
        "n_trades": float(len(trades)),
    }
