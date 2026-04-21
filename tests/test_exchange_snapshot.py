from unittest.mock import MagicMock

from crypto_bot.exchange_snapshot import build_snapshot


def test_build_snapshot_returns_expected_keys():
    ex = MagicMock()
    ex.fetch_balance.return_value = {"USDT": {"free": 100.0, "total": 100.0}}
    ex.fetch_ticker.return_value = {"symbol": "BTC/USDT", "last": 50_000.0}
    ex.fetch_open_orders.return_value = []
    ex.fetch_my_trades.return_value = []
    ex.fetch_time.return_value = 1_700_000_000_000
    ex.has = {"fetchStatus": False}

    data = build_snapshot(ex, ["BTC/USDT"])
    assert "balance" in data
    assert "tickers" in data
    assert "open_orders" in data
    assert "my_trades" in data
    assert "meta" in data
    assert data["meta"]["fetched_at"]
    assert data["balance"] is not None
