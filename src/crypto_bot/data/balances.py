from __future__ import annotations

from typing import Any

from crypto_bot.universe import TRACKED_BALANCE_ASSETS


def filtered_balance(exchange: Any) -> dict[str, dict[str, float]]:
    """
    Free/total for BTC, SOL, USDT only (Spot).
    """
    raw = exchange.fetch_balance()
    out: dict[str, dict[str, float]] = {}
    for asset in TRACKED_BALANCE_ASSETS:
        row = raw.get(asset, {}) if isinstance(raw, dict) else {}
        if isinstance(row, dict):
            free = float(row.get("free", 0) or 0)
            total = float(row.get("total", 0) or 0)
            out[asset] = {"free": free, "total": total}
        else:
            out[asset] = {"free": 0.0, "total": 0.0}
    return out


def portfolio_equity_usdt(
    balances: dict[str, dict[str, float]],
    last_prices: dict[str, float],
) -> float:
    """Approximate total equity in USDT using total balances and last prices per pair."""
    usdt = float(balances.get("USDT", {}).get("total", 0) or 0)
    for base in ("BTC", "SOL"):
        qty = float(balances.get(base, {}).get("total", 0) or 0)
        pair = f"{base}/USDT"
        px = float(last_prices.get(pair, 0) or 0)
        usdt += qty * px
    return usdt
