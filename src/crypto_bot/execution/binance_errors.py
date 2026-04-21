from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def call_with_exchange_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    base_delay: float = 0.5,
) -> T:
    """Retry on transient ccxt network / rate-limit style failures."""
    import ccxt  # local import

    last: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except (ccxt.NetworkError, ccxt.RequestTimeout, ccxt.ExchangeNotAvailable) as e:
            last = e
            logger.warning("exchange_retry", attempt=attempt + 1, error=str(e))
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2**attempt))
        except ccxt.DDoSProtection as e:
            last = e
            logger.warning("exchange_ddos_backoff", error=str(e))
            time.sleep(1.5)
        except Exception:
            raise
    assert last is not None
    raise last


def format_exchange_error(err: Exception) -> str:
    import ccxt

    if isinstance(err, ccxt.InsufficientFunds):
        return "Insufficient funds"
    if isinstance(err, ccxt.InvalidOrder):
        return f"Invalid order: {err}"
    if isinstance(err, (ccxt.NetworkError, ccxt.RequestTimeout)):
        return "Network error; try again"
    return str(err)[:200]
