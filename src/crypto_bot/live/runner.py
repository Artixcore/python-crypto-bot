from __future__ import annotations

import asyncio
import time as time_mod
from argparse import Namespace
from dataclasses import dataclass, field

import structlog

from crypto_bot.config.settings import AppSettings, TradingProfile
from crypto_bot.data.balances import filtered_balance, portfolio_equity_usdt
from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.data.cache import KlineCache
from crypto_bot.execution.order_router import OrderRequest, OrderRouter
from crypto_bot.features.indicators import add_basic_indicators, add_ma_rsi_indicators
from crypto_bot.journal.store import JournalStore
from crypto_bot.ml.filter import MLFilterConfig, augment_for_ml, load_ml_filter
from crypto_bot.monitoring.events import MetricsSink, emit
from crypto_bot.paper.sim_broker import PaperBroker
from crypto_bot.risk.governor import RiskDecision, RiskGovernor, RiskLimits
from crypto_bot.risk.policy import ExitPlan, StopTakePolicy, check_exit_long, initial_plan_for_long
from crypto_bot.risk.position_sizing import fixed_pct_of_equity_size
from crypto_bot.strategies.base import StrategySignal
from crypto_bot.strategies.ma_rsi import MaRsiParams, ma_rsi_signals
from crypto_bot.universe import parse_run_symbols_arg

logger = structlog.get_logger(__name__)


@dataclass
class RunnerState:
    in_position: bool = False
    base_qty: float = 0.0
    entry_price: float = 0.0
    exit_plan: ExitPlan | None = None


@dataclass
class LiveContext:
    settings: AppSettings
    symbols: list[str]
    timeframe: str
    client: BinanceSpotClient
    cache: KlineCache
    journal: JournalStore
    metrics: MetricsSink = field(default_factory=MetricsSink)
    risk: RiskGovernor = field(default_factory=RiskGovernor)
    states: dict[str, RunnerState] = field(default_factory=dict)
    stop_take: StopTakePolicy = field(default_factory=StopTakePolicy)
    ml_filter: object | None = None


def _want_long(feats, settings: AppSettings) -> bool:
    p = MaRsiParams(rsi_buy_max=settings.rsi_buy_max, rsi_exit_min=settings.rsi_exit_min)
    sig = ma_rsi_signals(feats, p)
    return bool(sig.iloc[-1] == StrategySignal.LONG)


def _last_prices(client: BinanceSpotClient, symbols: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for sym in symbols:
        try:
            t = client.fetch_ticker(sym)
            out[sym] = float(t.get("last") or t.get("close") or 0)
        except Exception:
            out[sym] = 0.0
    return out


def _equity(
    settings: AppSettings,
    client: BinanceSpotClient,
    paper: PaperBroker | None,
    symbols: list[str],
    lasts: dict[str, float],
) -> float:
    if paper is not None:
        return paper.equity_usdt(lasts)
    if settings.profile == TradingProfile.LIVE and settings.live_allowed():
        try:
            bal = filtered_balance(client.exchange)
            return portfolio_equity_usdt(bal, lasts)
        except Exception:
            return 10_000.0
    return 10_000.0


def _open_position_count(states: dict[str, RunnerState]) -> int:
    return sum(1 for s in states.values() if s.in_position)


async def run_loop(args: Namespace, settings: AppSettings) -> int:
    from crypto_bot.logging_setup import configure_logging

    configure_logging()

    symbols = parse_run_symbols_arg(args.symbols)
    client = BinanceSpotClient(
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    cache = KlineCache(settings.data_dir)
    journal = JournalStore(settings.journal_path)
    risk = RiskGovernor(
        limits=RiskLimits(max_open_positions=len(symbols)),
        kill_switch=settings.kill_switch,
    )

    ml_model = None
    if (
        settings.ml_enabled
        and settings.ml_model_path
        and settings.ml_model_path.exists()
    ):
        ml_model = load_ml_filter(settings.ml_model_path, MLFilterConfig(shadow=settings.ml_shadow))

    ctx = LiveContext(
        settings=settings,
        symbols=symbols,
        timeframe=args.timeframe,
        client=client,
        cache=cache,
        journal=journal,
        risk=risk,
        states={s: RunnerState() for s in symbols},
        ml_filter=ml_model,
    )

    if settings.profile == TradingProfile.LIVE and not settings.live_allowed():
        logger.error("live_not_allowed", profile=settings.profile, live_confirm=settings.live_confirm)
        journal.write("live_blocked", {"reason": "live_not_allowed"})
        return 2

    paper_broker: PaperBroker | None = None
    router: OrderRouter | None = None
    if settings.profile == TradingProfile.PAPER:
        paper_broker = PaperBroker(quote_balance=10_000.0)
    elif settings.profile == TradingProfile.LIVE and settings.live_allowed():
        router = OrderRouter(client)

    emit(
        "runner_start",
        profile=settings.profile.value,
        symbols=symbols,
        dry_run=settings.dry_run,
    )

    try:
        while True:
            lasts = _last_prices(client, symbols)
            for sym in symbols:
                await _tick_symbol(ctx, sym, args, paper_broker, router, lasts)
            await asyncio.sleep(args.interval_sec)
    except KeyboardInterrupt:
        logger.info("runner_stop", reason="keyboard_interrupt")
        return 0


async def _tick_symbol(
    ctx: LiveContext,
    symbol: str,
    args: Namespace,
    paper: PaperBroker | None,
    router: OrderRouter | None,
    lasts: dict[str, float],
) -> None:
    t0 = time_mod.perf_counter()
    settings = ctx.settings
    st = ctx.states[symbol]

    df = ctx.cache.fetch_or_load(
        ctx.client,
        symbol,
        ctx.timeframe,
        limit=500,
        force_refresh=True,
    )
    feats = add_ma_rsi_indicators(
        df,
        ma_fast=settings.ma_fast_period,
        ma_slow=settings.ma_slow_period,
        rsi_period=settings.rsi_period,
    ).dropna()
    if feats.empty:
        return

    last = float(feats["close"].iloc[-1])
    high = float(feats["high"].iloc[-1])
    low = float(feats["low"].iloc[-1])
    atr = float(feats["atr"].iloc[-1])

    want = _want_long(feats, settings)
    ml_ok = True
    ml_score = None
    if ctx.ml_filter is not None:
        feats_ml_base = add_basic_indicators(df).dropna()
        if not feats_ml_base.empty:
            feats_ml = augment_for_ml(feats_ml_base)
            ml_ok, ml_score = ctx.ml_filter.allow(feats_ml)

    ctx.journal.write(
        "tick",
        {
            "symbol": symbol,
            "want_long": want,
            "ml_ok": ml_ok,
            "ml_score": ml_score,
            "in_position": st.in_position,
        },
    )

    equity = _equity(settings, ctx.client, paper, ctx.symbols, lasts)
    open_n = _open_position_count(ctx.states)

    if st.in_position and st.exit_plan is not None:
        plan = st.exit_plan
        exit_hit, exit_px, reason = check_exit_long(low, high, last, plan)
        if exit_hit or not want:
            _close_symbol(ctx, symbol, paper, router, exit_px if exit_hit else last, reason or "signal_flat")
            ctx.metrics.observe_latency("tick_ms", (time_mod.perf_counter() - t0) * 1000.0)
            return

    if st.in_position:
        ctx.metrics.observe_latency("tick_ms", (time_mod.perf_counter() - t0) * 1000.0)
        return

    if not want or not ml_ok:
        ctx.metrics.observe_latency("tick_ms", (time_mod.perf_counter() - t0) * 1000.0)
        return

    stop_px = last - ctx.stop_take.atr_stop_mult * atr
    qty = fixed_pct_of_equity_size(equity, last, settings.position_size_pct_of_equity)
    notional = qty * last

    decision, rreason = ctx.risk.pre_trade(equity, notional, open_n)
    if decision != RiskDecision.ALLOW:
        emit("risk_block", decision=decision.value, reason=rreason, symbol=symbol)
        ctx.journal.write("risk", {"symbol": symbol, "decision": decision.value, "reason": rreason})
        ctx.metrics.inc(f"risk_{decision.value}")
        return

    if settings.dry_run:
        emit("dry_run_order", side="buy", qty=qty, notional=notional, symbol=symbol)
        ctx.journal.write("dry_run", {"symbol": symbol, "qty": qty, "notional": notional})
        ctx.metrics.inc("dry_run")
        return

    if settings.profile == TradingProfile.DEV:
        emit("dev_signal", qty=qty, want_long=True, symbol=symbol)
        ctx.journal.write("dev_skip", {"symbol": symbol, "qty": qty})
        return

    if paper is not None:
        req = OrderRequest(symbol=symbol, side="buy", type="market", amount=qty, tag="paper_entry")
        try:
            paper.market(req, mid_price=last)
            ctx.risk.on_order_submitted()
            st.in_position = True
            st.base_qty = paper.base_for(symbol)
            st.entry_price = last
            st.exit_plan = initial_plan_for_long(last, atr, ctx.stop_take)
            ctx.journal.write("paper_buy", {"symbol": symbol, "qty": qty, "stop": st.exit_plan.stop_price})
        except Exception as e:
            logger.exception("paper_order_failed", error=str(e), symbol=symbol)
            ctx.journal.write("paper_error", {"symbol": symbol, "error": str(e)})
        return

    if router is not None:
        req = OrderRequest(
            symbol=symbol,
            side="buy",
            type="market",
            amount=qty,
            strategy_id="ma_rsi",
            tag="entry",
        )
        try:
            router.place(req)
            ctx.risk.on_order_submitted()
            st.in_position = True
            st.entry_price = last
            st.base_qty = qty
            st.exit_plan = initial_plan_for_long(last, atr, ctx.stop_take)
            ctx.journal.write("live_buy", {"symbol": symbol, "qty": qty})
        except Exception as e:
            logger.exception("live_order_failed", error=str(e), symbol=symbol)
            ctx.journal.write("live_error", {"symbol": symbol, "error": str(e)})

    ctx.metrics.observe_latency("tick_ms", (time_mod.perf_counter() - t0) * 1000.0)


def _close_symbol(
    ctx: LiveContext,
    symbol: str,
    paper: PaperBroker | None,
    router: OrderRouter | None,
    exit_px: float,
    reason: str,
) -> None:
    st = ctx.states[symbol]
    if paper is not None and st.base_qty > 0:
        req = OrderRequest(
            symbol=symbol,
            side="sell",
            type="market",
            amount=st.base_qty,
            tag="paper_exit",
        )
        try:
            paper.market(req, mid_price=exit_px)
            pnl = (exit_px - st.entry_price) * st.base_qty
            ctx.risk.register_fill_pnl(pnl)
            ctx.journal.write("paper_sell", {"symbol": symbol, "reason": reason, "pnl": pnl})
        except Exception as e:
            logger.exception("paper_exit_failed", error=str(e), symbol=symbol)
    elif router is not None and st.base_qty > 0:
        req = OrderRequest(
            symbol=symbol,
            side="sell",
            type="market",
            amount=st.base_qty,
            strategy_id="ma_rsi",
            tag="exit",
        )
        try:
            router.place(req)
            ctx.journal.write("live_sell", {"symbol": symbol, "reason": reason})
        except Exception as e:
            logger.exception("live_exit_failed", error=str(e), symbol=symbol)

    st.in_position = False
    st.base_qty = 0.0
    st.entry_price = 0.0
    st.exit_plan = None
