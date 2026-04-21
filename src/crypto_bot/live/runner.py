from __future__ import annotations

import asyncio
import time as time_mod
from argparse import Namespace
from dataclasses import dataclass, field

import structlog

from crypto_bot.config.settings import AppSettings, TradingProfile
from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.data.cache import KlineCache
from crypto_bot.execution.order_router import OrderRequest, OrderRouter
from crypto_bot.features.indicators import add_basic_indicators
from crypto_bot.journal.store import JournalStore
from crypto_bot.ml.filter import MLFilterConfig, augment_for_ml, load_ml_filter
from crypto_bot.monitoring.events import MetricsSink, emit
from crypto_bot.paper.sim_broker import PaperBroker
from crypto_bot.risk.governor import RiskDecision, RiskGovernor, RiskLimits
from crypto_bot.risk.policy import ExitPlan, StopTakePolicy, check_exit_long, initial_plan_for_long
from crypto_bot.risk.position_sizing import risk_based_size
from crypto_bot.strategies.base import StrategySignal
from crypto_bot.strategies.trend_pullback import trend_pullback_signals

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
    symbol: str
    timeframe: str
    client: BinanceSpotClient
    cache: KlineCache
    journal: JournalStore
    metrics: MetricsSink = field(default_factory=MetricsSink)
    risk: RiskGovernor = field(default_factory=RiskGovernor)
    state: RunnerState = field(default_factory=RunnerState)
    stop_take: StopTakePolicy = field(default_factory=StopTakePolicy)
    ml_filter: object | None = None


def _want_long(feats) -> bool:
    sig = trend_pullback_signals(feats)
    return bool(sig.iloc[-1] == StrategySignal.LONG)


def _equity_paper(paper: PaperBroker, last_px: float) -> float:
    return float(paper.quote_balance + paper.base_position * last_px)


def _equity_live(client: BinanceSpotClient, symbol: str) -> float:
    bal = client.exchange.fetch_balance()
    quote = symbol.split("/")[1]
    base = symbol.split("/")[0]
    free_quote = float(bal.get(quote, {}).get("total", 0) or 0)
    free_base = float(bal.get(base, {}).get("total", 0) or 0)
    ticker = client.fetch_ticker(symbol)
    px = float(ticker.get("last") or ticker.get("close") or 0)
    return free_quote + free_base * px


async def run_loop(args: Namespace, settings: AppSettings) -> int:
    from crypto_bot.logging_setup import configure_logging

    configure_logging()

    client = BinanceSpotClient(
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    cache = KlineCache(settings.data_dir)
    journal = JournalStore(settings.journal_path)
    risk = RiskGovernor(limits=RiskLimits(), kill_switch=settings.kill_switch)

    ml_model = None
    if settings.ml_model_path and settings.ml_model_path.exists():
        ml_model = load_ml_filter(settings.ml_model_path, MLFilterConfig(shadow=settings.ml_shadow))

    ctx = LiveContext(
        settings=settings,
        symbol=args.symbol,
        timeframe=args.timeframe,
        client=client,
        cache=cache,
        journal=journal,
        risk=risk,
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
        symbol=args.symbol,
        dry_run=settings.dry_run,
    )

    try:
        while True:
            await _tick(ctx, args, paper_broker, router)
            await asyncio.sleep(args.interval_sec)
    except KeyboardInterrupt:
        logger.info("runner_stop", reason="keyboard_interrupt")
        return 0


async def _tick(
    ctx: LiveContext,
    args: Namespace,
    paper: PaperBroker | None,
    router: OrderRouter | None,
) -> None:
    t0 = time_mod.perf_counter()
    df = ctx.cache.fetch_or_load(
        ctx.client,
        ctx.symbol,
        ctx.timeframe,
        limit=500,
        force_refresh=True,
    )
    feats = add_basic_indicators(df).dropna()
    if feats.empty:
        return

    last = float(feats["close"].iloc[-1])
    high = float(feats["high"].iloc[-1])
    low = float(feats["low"].iloc[-1])
    atr = float(feats["atr"].iloc[-1])

    want = _want_long(feats)
    ml_ok = True
    ml_score = None
    feats_ml = augment_for_ml(feats)
    if ctx.ml_filter is not None:
        ml_ok, ml_score = ctx.ml_filter.allow(feats_ml)

    ctx.journal.write(
        "tick",
        {
            "symbol": ctx.symbol,
            "want_long": want,
            "ml_ok": ml_ok,
            "ml_score": ml_score,
            "in_position": ctx.state.in_position,
        },
    )

    if paper is not None:
        equity = _equity_paper(paper, last)
    elif ctx.settings.profile == TradingProfile.LIVE and ctx.settings.live_allowed():
        try:
            equity = _equity_live(ctx.client, ctx.symbol)
        except Exception:
            equity = 10_000.0
    else:
        equity = 10_000.0

    open_positions = 1 if ctx.state.in_position else 0

    if ctx.state.in_position and ctx.state.exit_plan is not None:
        plan = ctx.state.exit_plan
        exit_hit, exit_px, reason = check_exit_long(low, high, last, plan)
        if exit_hit or not want:
            _close_position(ctx, paper, router, exit_px if exit_hit else last, reason or "signal_flat")
            elapsed = (time_mod.perf_counter() - t0) * 1000.0
            ctx.metrics.observe_latency("tick_ms", elapsed)
            return

    if ctx.state.in_position:
        elapsed = (time_mod.perf_counter() - t0) * 1000.0
        ctx.metrics.observe_latency("tick_ms", elapsed)
        return

    if not want or not ml_ok:
        elapsed = (time_mod.perf_counter() - t0) * 1000.0
        ctx.metrics.observe_latency("tick_ms", elapsed)
        return

    stop_px = last - ctx.stop_take.atr_stop_mult * atr
    qty = risk_based_size(equity, last, stop_px, 0.005)
    notional = qty * last

    decision, reason = ctx.risk.pre_trade(equity, notional, open_positions)
    if decision != RiskDecision.ALLOW:
        emit("risk_block", decision=decision.value, reason=reason)
        ctx.journal.write("risk", {"decision": decision.value, "reason": reason})
        ctx.metrics.inc(f"risk_{decision.value}")
        return

    if ctx.settings.dry_run:
        emit("dry_run_order", side="buy", qty=qty, notional=notional)
        ctx.journal.write("dry_run", {"qty": qty, "notional": notional})
        ctx.metrics.inc("dry_run")
        return

    if ctx.settings.profile == TradingProfile.DEV:
        emit("dev_signal", qty=qty, want_long=True)
        ctx.journal.write("dev_skip", {"qty": qty})
        return

    if paper is not None:
        req = OrderRequest(symbol=ctx.symbol, side="buy", type="market", amount=qty, tag="paper_entry")
        try:
            paper.market(req, mid_price=last)
            ctx.risk.on_order_submitted()
            ctx.state.in_position = True
            ctx.state.base_qty = paper.base_position
            ctx.state.entry_price = last
            ctx.state.exit_plan = initial_plan_for_long(last, atr, ctx.stop_take)
            ctx.journal.write("paper_buy", {"qty": qty, "stop": ctx.state.exit_plan.stop_price})
        except Exception as e:
            logger.exception("paper_order_failed", error=str(e))
            ctx.journal.write("paper_error", {"error": str(e)})
        return

    if router is not None:
        req = OrderRequest(
            symbol=ctx.symbol,
            side="buy",
            type="market",
            amount=qty,
            strategy_id="trend_pullback",
            tag="entry",
        )
        try:
            router.place(req)
            ctx.risk.on_order_submitted()
            ctx.state.in_position = True
            ctx.state.entry_price = last
            ctx.state.base_qty = qty
            ctx.state.exit_plan = initial_plan_for_long(last, atr, ctx.stop_take)
            ctx.journal.write("live_buy", {"qty": qty})
        except Exception as e:
            logger.exception("live_order_failed", error=str(e))
            ctx.journal.write("live_error", {"error": str(e)})

    elapsed = (time_mod.perf_counter() - t0) * 1000.0
    ctx.metrics.observe_latency("tick_ms", elapsed)


def _close_position(
    ctx: LiveContext,
    paper: PaperBroker | None,
    router: OrderRouter | None,
    exit_px: float,
    reason: str,
) -> None:
    if paper is not None and ctx.state.base_qty > 0:
        req = OrderRequest(
            symbol=ctx.symbol,
            side="sell",
            type="market",
            amount=ctx.state.base_qty,
            tag="paper_exit",
        )
        try:
            paper.market(req, mid_price=exit_px)
            pnl = (exit_px - ctx.state.entry_price) * ctx.state.base_qty
            ctx.risk.register_fill_pnl(pnl)
            ctx.journal.write("paper_sell", {"reason": reason, "pnl": pnl})
        except Exception as e:
            logger.exception("paper_exit_failed", error=str(e))
    elif router is not None and ctx.state.base_qty > 0:
        req = OrderRequest(
            symbol=ctx.symbol,
            side="sell",
            type="market",
            amount=ctx.state.base_qty,
            strategy_id="trend_pullback",
            tag="exit",
        )
        try:
            router.place(req)
            ctx.journal.write("live_sell", {"reason": reason})
        except Exception as e:
            logger.exception("live_exit_failed", error=str(e))

    ctx.state.in_position = False
    ctx.state.base_qty = 0.0
    ctx.state.entry_price = 0.0
    ctx.state.exit_plan = None
