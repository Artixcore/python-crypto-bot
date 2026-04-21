from __future__ import annotations

from typing import Any

from crypto_bot.universe import TRACKED_BALANCE_ASSETS


def _row_for_asset(raw: dict[str, Any], asset: str) -> dict[str, float]:
    """
    ccxt can return balances as:
    - unified: raw['BTC'] = {'free', 'used', 'total'}
    - indexed: raw['free']['BTC'], raw['total']['BTC']
    """
    if not isinstance(raw, dict):
        return {"free": 0.0, "total": 0.0}

    cur = raw.get(asset)
    if isinstance(cur, dict) and ("free" in cur or "total" in cur or "used" in cur):
        free = float(cur.get("free", 0) or 0)
        total = cur.get("total")
        if total is None:
            total = free + float(cur.get("used", 0) or 0)
        else:
            total = float(total or 0)
        return {"free": free, "total": float(total)}

    free_map = raw.get("free")
    total_map = raw.get("total")
    if isinstance(free_map, dict) and asset in free_map:
        f = float(free_map.get(asset, 0) or 0)
        t = f
        if isinstance(total_map, dict) and asset in total_map:
            t = float(total_map.get(asset, 0) or 0)
        return {"free": f, "total": t}

    return {"free": 0.0, "total": 0.0}


def filtered_balance(exchange: Any) -> dict[str, dict[str, float]]:
    """
    Free/total for BTC, SOL, USDT only (Spot).
    """
    raw = exchange.fetch_balance()
    out: dict[str, dict[str, float]] = {}
    for asset in TRACKED_BALANCE_ASSETS:
        out[asset] = _row_for_asset(raw, asset)
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
