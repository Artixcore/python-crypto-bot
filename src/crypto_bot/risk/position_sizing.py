from __future__ import annotations


def risk_based_size(
    equity: float,
    entry_price: float,
    stop_price: float,
    risk_fraction: float,
    *,
    min_notional: float = 10.0,
    max_notional_fraction: float = 0.25,
) -> float:
    """
    Position size in base asset units from fixed fractional risk.
    stop_distance = abs(entry - stop) / entry (approx for small moves).
    """
    if equity <= 0 or entry_price <= 0:
        return 0.0
    stop_dist = abs(entry_price - stop_price) / entry_price
    if stop_dist <= 0:
        return 0.0
    risk_dollars = equity * risk_fraction
    size = risk_dollars / (entry_price * stop_dist)
    max_size = (equity * max_notional_fraction) / entry_price
    size = min(size, max_size)
    if size * entry_price < min_notional:
        return 0.0
    return float(size)
