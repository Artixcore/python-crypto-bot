from __future__ import annotations

import json
from html import escape
from typing import Any

from crypto_bot.config.settings import AppSettings, TradingProfile
from crypto_bot.data.balances import portfolio_equity_usdt
from crypto_bot.data.cache import KlineCache
from crypto_bot.features.indicators import add_ma_rsi_indicators
from crypto_bot.journal.store import JournalStore
from crypto_bot.strategies.ma_rsi import MaRsiParams, ma_rsi_signals
from crypto_bot.telegram_bot.formatting import split_telegram_chunks

MAX_HTML_LEN = 3800


def _e(x: object) -> str:
    return escape(str(x), quote=False)


def _fmt_float(x: float | None, *, digits: int = 4) -> str:
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if abs(v) >= 1_000_000:
        return f"{v:,.{digits}f}".rstrip("0").rstrip(".")
    if abs(v) >= 1:
        return f"{v:,.{digits}f}".rstrip("0").rstrip(".")
    return f"{v:.{max(digits, 8)}f}".rstrip("0").rstrip(".")


def _last_prices_from_snapshot(snap: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for sym, t in (snap.get("tickers") or {}).items():
        if isinstance(t, dict) and t.get("last") is not None:
            try:
                out[str(sym)] = float(t["last"])
            except (TypeError, ValueError):
                continue
    return out


def _truncate_html(html: str) -> str:
    if len(html) <= MAX_HTML_LEN:
        return html
    return html[: MAX_HTML_LEN - 20] + "\n…</i>"


def format_hub_html(settings: AppSettings, snap: dict[str, Any]) -> str:
    bal = snap.get("balance") or {}
    lasts = _last_prices_from_snapshot(snap)
    equity: float | None = None
    if isinstance(bal, dict) and lasts:
        try:
            equity = portfolio_equity_usdt(bal, lasts)
        except Exception:
            equity = None
    usdt_free = "—"
    if isinstance(bal, dict):
        u = bal.get("USDT")
        if isinstance(u, dict) and u.get("free") is not None:
            usdt_free = _fmt_float(float(u["free"]), digits=2)

    line_eq = _fmt_float(equity, digits=2) if equity is not None else "—"
    meta = snap.get("meta") or {}
    err = meta.get("error")
    warn = ""
    if err:
        warn = f"\n⚠ {_e(err[:400])}"

    return _truncate_html(
        "<b>Spot terminal</b> · Binance BTC/SOL\n"
        f"Profile: <code>{_e(settings.profile.value)}</code> · "
        f"USDT avail: <code>{_e(usdt_free)}</code>\n"
        f"Portfolio equity (mark): <code>{_e(line_eq)} USDT</code>\n"
        f"<i>Runner is not controlled here — use CLI for start/stop. "
        f"Tap a section below.</i>{warn}",
    )


def format_account_html(settings: AppSettings, snap: dict[str, Any]) -> str:
    bal = snap.get("balance") or {}
    lasts = _last_prices_from_snapshot(snap)
    equity: float | None = None
    if isinstance(bal, dict) and lasts:
        try:
            equity = portfolio_equity_usdt(bal, lasts)
        except Exception:
            equity = None

    rows: list[str] = []
    rows.append("<b>Account</b>")
    meta = snap.get("meta") or {}
    rows.append(f"Snapshot: <code>{_e(meta.get('fetched_at', '—'))}</code>")
    if meta.get("error"):
        rows.append(f"⚠ <code>{_e(str(meta.get('error'))[:500])}</code>")

    if isinstance(bal, dict):
        rows.append("")
        rows.append("<b>Balances</b> (tracked)")
        rows.append("<pre>")
        for asset in ("USDT", "BTC", "SOL"):
            r = bal.get(asset) or {}
            if isinstance(r, dict):
                free = r.get("free", "—")
                total = r.get("total", "—")
                rows.append(f"{_e(asset)}  free {_e(free)}  total {_e(total)}")
        rows.append("</pre>")

    eq_s = _fmt_float(equity, digits=2) if equity is not None else "—"
    rows.append("")
    rows.append(f"<b>Portfolio equity (mark)</b>: <code>{_e(eq_s)} USDT</code>")
    rows.append("<i>Spot: no leverage. Equity uses last prices from snapshot tickers.</i>")
    return _truncate_html("\n".join(rows))


def format_markets_html(snap: dict[str, Any]) -> str:
    rows: list[str] = ["<b>Markets</b>", ""]
    tickers = snap.get("tickers") or {}
    if not tickers:
        rows.append("<i>No ticker data.</i>")
        return _truncate_html("\n".join(rows))

    rows.append("<pre>")
    for sym in sorted(tickers.keys()):
        t = tickers[sym]
        if not isinstance(t, dict):
            continue
        last = t.get("last", "—")
        chg = t.get("percentage")
        chg_s = "—"
        if chg is not None:
            try:
                chg_s = f"{float(chg):+.2f}%"
            except (TypeError, ValueError):
                chg_s = str(chg)
        hi = t.get("high")
        lo = t.get("low")
        rows.append(f"{_e(sym)}  last={_e(last)}  24h={_e(chg_s)}")
        if hi is not None and lo is not None:
            rows.append(f"         range {_e(lo)} – {_e(hi)}")
    rows.append("</pre>")
    return _truncate_html("\n".join(rows))


def _summarize_order(o: dict[str, Any]) -> str:
    return (
        f"{_e(o.get('symbol', '?'))} {_e(o.get('side', '?'))} "
        f"{_e(o.get('type', '?'))} amt={_e(o.get('amount', '?'))} "
        f"price={_e(o.get('price', '?'))}"
    )


def _summarize_trade(tr: dict[str, Any]) -> str:
    side = tr.get("side", "?")
    sym = tr.get("symbol", "?")
    amt = tr.get("amount", "?")
    price = tr.get("price", "?")
    tid = tr.get("id", "?")
    return f"{_e(sym)} {_e(side)} {_e(amt)} @ {_e(price)}  id={_e(tid)}"


def format_orders_and_fills_html(snap: dict[str, Any], *, max_orders: int = 12, max_trades: int = 10) -> str:
    rows: list[str] = ["<b>Orders &amp; activity</b>", ""]
    oo = snap.get("open_orders")
    if isinstance(oo, list):
        rows.append(f"<b>Open orders</b> ({len(oo)})")
        if not oo:
            rows.append("<i>None</i>")
        else:
            rows.append("<pre>")
            for o in oo[:max_orders]:
                if isinstance(o, dict):
                    rows.append(_summarize_order(o))
            if len(oo) > max_orders:
                rows.append(f"... +{len(oo) - max_orders} more")
            rows.append("</pre>")
    else:
        rows.append("<b>Open orders</b>: <i>unavailable</i>")

    rows.append("")
    mt = snap.get("my_trades") or {}
    rows.append("<b>Recent fills</b> (exchange, per pair)")
    if isinstance(mt, dict):
        any_tr = False
        for sym in sorted(mt.keys()):
            trades = mt.get(sym)
            if not isinstance(trades, list):
                continue
            if not trades:
                continue
            any_tr = True
            rows.append(f"\n<code>{_e(sym)}</code>")
            rows.append("<pre>")
            for tr in trades[-max_trades:]:
                if isinstance(tr, dict):
                    rows.append(_summarize_trade(tr))
            rows.append("</pre>")
        if not any_tr:
            rows.append("<i>No recent trades returned.</i>")
    return _truncate_html("\n".join(rows))


def format_strategy_risk_html(
    settings: AppSettings,
    journal: JournalStore,
) -> str:
    paper = journal.paper_sell_summary(limit=800)
    wr = paper["win_rate_pct"]
    n = paper["closed_with_pnl_count"]
    pnl = paper["total_pnl"]
    pnl_s = _fmt_float(pnl, digits=4)
    rows: list[str] = [
        "<b>Strategy &amp; risk</b>",
        "",
        f"Profile: <code>{_e(settings.profile.value)}</code>",
        f"Dry run: <code>{settings.dry_run}</code> · Kill switch: <code>{settings.kill_switch}</code>",
        f"Telegram trading: <code>{settings.telegram_trading_enabled}</code>",
        "",
        "<b>Strategy params</b> (MA + RSI)",
        f"Position size % of equity: <code>{_e(settings.position_size_pct_of_equity)}</code>",
        f"MA fast/slow: <code>{settings.ma_fast_period}</code>/<code>{settings.ma_slow_period}</code>",
        f"RSI period / buy max / exit min: <code>{settings.rsi_period}</code> / "
        f"<code>{settings.rsi_buy_max}</code> / <code>{settings.rsi_exit_min}</code>",
        "",
        "<b>Paper journal (closed)</b>",
        f"Win rate (paper PnL rows): <code>{wr:.1f}%</code> over <code>{n}</code> closes",
        f"Sum PnL (paper): <code>{_e(pnl_s)} USDT</code>",
        "<i>Live realized PnL is not fully tracked in journal; use exchange history for live.</i>",
        "",
        "<b>Risk adjustment</b>",
        "<i>Change sizing and limits via env / config (e.g. CRYPTO_BOT_POSITION_SIZE_PCT_OF_EQUITY, "
        "CRYPTO_BOT_KILL_SWITCH). No hot-reload from Telegram.</i>",
        "",
        "<i>The live runner process is started separately; this chat does not start or stop it.</i>",
    ]
    return _truncate_html("\n".join(rows))


def format_execution_log_html(journal: JournalStore, *, limit: int = 35) -> str:
    rows: list[str] = ["<b>Execution log</b> (journal)", ""]
    evs = journal.recent_events(limit=limit)
    if not evs:
        rows.append("<i>No journal events yet.</i>")
        return _truncate_html("\n".join(rows))

    rows.append("<pre>")
    for r in evs:
        payload = r.get("payload") or {}
        brief = json.dumps(payload, ensure_ascii=False, default=str)
        if len(brief) > 160:
            brief = brief[:157] + "..."
        line = f"{_e(r.get('ts', '?'))}  {_e(r.get('event', '?'))}  {escape(brief, quote=False)}"
        rows.append(line)
    rows.append("</pre>")
    return _truncate_html("\n".join(rows))


def format_signals_html(
    settings: AppSettings,
    journal: JournalStore,
    indicator_lines: list[str] | None,
) -> str:
    ticks = journal.last_tick_by_symbol()
    rows: list[str] = [
        "<b>Live signals</b>",
        "<i>Journal snapshot — not a substitute for full runner state.</i>",
        "",
    ]
    if not ticks:
        rows.append("<i>No tick events in journal.</i>")
    else:
        rows.append("<pre>")
        for sym in sorted(ticks.keys()):
            t = ticks[sym]
            wl = t.get("want_long")
            ml = t.get("ml_ok")
            ip = t.get("in_position")
            rows.append(
                f"{_e(sym):10}  want_long={_e(wl)}  in_pos={_e(ip)}  ml_ok={_e(ml)}",
            )
        rows.append("</pre>")

    rows.append("")
    rows.append("<b>Indicative strategy row</b> (last closed bar)")
    if indicator_lines:
        rows.append("<pre>")
        for line in indicator_lines:
            rows.append(_e(line))
        rows.append("</pre>")
    else:
        rows.append("<i>Unavailable (no OHLCV or same as journal).</i>")

    rows.append("")
    rows.append(f"RSI buy / exit thresholds: <code>{settings.rsi_buy_max}</code> / "
                f"<code>{settings.rsi_exit_min}</code>")
    return _truncate_html("\n".join(rows))


def format_trade_help_html(settings: AppSettings) -> str:
    live_ok = settings.profile == TradingProfile.LIVE and settings.live_allowed()
    trading_on = settings.telegram_trading_enabled and live_ok
    gate = "<b>Trading unlocked</b>" if trading_on else "<b>Trading locked</b>"
    reason = []
    if not settings.telegram_trading_enabled:
        reason.append("Set CRYPTO_BOT_TELEGRAM_TRADING_ENABLED=yes")
    if settings.profile != TradingProfile.LIVE or not settings.live_allowed():
        reason.append("Require PROFILE=live, API keys, CRYPTO_BOT_LIVE_CONFIRM=yes")
    reason_s = "; ".join(reason) if reason else "OK"

    return _truncate_html(
        "<b>Trade</b> (market, Spot)\n\n"
        f"{gate}\n"
        f"<i>{_e(reason_s)}</i>\n\n"
        "<b>Commands</b>\n"
        "<code>/buy BTC 25</code> — spend ~25 USDT on BTC\n"
        "<code>/sell SOL 0.5</code> — sell 0.5 SOL\n\n"
        "<i>Market orders only. Confirm keys and risk before live.</i>",
    )


def format_help_html() -> str:
    return _truncate_html(
        "<b>Commands</b>\n"
        "<code>/start</code> — main menu\n"
        "<code>/ping</code> — health (no exchange)\n"
        "<code>/balance</code> — balances\n"
        "<code>/status</code> — slim status\n"
        "<code>/snapshot</code> — raw JSON snapshot\n"
        "<code>/buy</code> <code>/sell</code> — see Trade panel\n",
    )


def chunks_for_telegram(html: str) -> list[str]:
    return split_telegram_chunks(html, max_len=4096)


def build_indicator_lines(client: Any, settings: AppSettings, *, timeframe: str = "1h") -> list[str] | None:
    """
    Last closed-bar MA/RSI snapshot per configured pair (cache-backed, read-only).
    """
    cache = KlineCache(settings.data_dir)
    p = MaRsiParams(rsi_buy_max=settings.rsi_buy_max, rsi_exit_min=settings.rsi_exit_min)
    lines: list[str] = []
    for sym in settings.snapshot_symbol_list():
        try:
            df = cache.fetch_or_load(client, sym, timeframe, limit=250, force_refresh=False)
            feats = add_ma_rsi_indicators(
                df,
                ma_fast=settings.ma_fast_period,
                ma_slow=settings.ma_slow_period,
                rsi_period=settings.rsi_period,
            ).dropna()
            if feats.empty:
                continue
            sig = ma_rsi_signals(feats, p)
            last = feats.iloc[-1]
            lines.append(
                f"{sym}  close={float(last['close']):.4f}  "
                f"RSI={float(last['rsi']):.1f}  "
                f"sig={int(sig.iloc[-1])}",
            )
        except Exception:
            continue
    return lines or None
