from __future__ import annotations

QUOTE = "USDT"
BASE_ASSETS = ("BTC", "SOL")
TRADING_PAIRS: tuple[str, ...] = ("BTC/USDT", "SOL/USDT")
TRACKED_BALANCE_ASSETS: tuple[str, ...] = ("BTC", "SOL", "USDT")


def is_allowed_trading_pair(symbol: str) -> bool:
    s = symbol.strip().upper().replace(" ", "")
    return s in TRADING_PAIRS


def parse_pair_or_raise(symbol: str) -> str:
    s = symbol.strip().upper().replace(" ", "")
    if s not in TRADING_PAIRS:
        raise ValueError(f"Only {TRADING_PAIRS} are allowed, got {symbol!r}")
    return s


def normalize_symbol_list(raw: str) -> list[str]:
    """Return ordered list of valid trading pairs from comma-separated input."""
    out: list[str] = []
    for part in raw.split(","):
        p = part.strip().upper().replace(" ", "")
        if not p:
            continue
        if p in TRADING_PAIRS and p not in out:
            out.append(p)
    return out if out else list(TRADING_PAIRS)


def parse_run_symbols_arg(symbols_csv: str) -> list[str]:
    return normalize_symbol_list(symbols_csv)
