from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from crypto_bot.dashboard.app import create_app


def test_snapshot_endpoint_returns_json_keys():
    ex = MagicMock()
    ex.load_markets = MagicMock()
    ex.fetch_balance.return_value = {"USDT": {"free": 100.0, "total": 100.0}}
    ex.fetch_ticker.return_value = {"symbol": "BTC/USDT", "last": 50000.0}
    ex.fetch_open_orders.return_value = []
    ex.fetch_my_trades.return_value = []
    ex.fetch_time.return_value = 1_700_000_000_000
    ex.has = {"fetchStatus": False}

    client_wrapped = MagicMock()
    client_wrapped.exchange = ex

    with patch("crypto_bot.dashboard.app._make_client", return_value=client_wrapped):
        with TestClient(create_app()) as tc:
            r = tc.get("/api/snapshot")
    assert r.status_code == 200
    data = r.json()
    assert "balance" in data
    assert "tickers" in data
    assert "open_orders" in data
    assert "my_trades" in data
    assert "meta" in data
    assert data["meta"]["fetched_at"]
    assert data["balance"] is not None


def test_index_returns_html():
    ex = MagicMock()
    ex.load_markets = MagicMock()
    client_wrapped = MagicMock()
    client_wrapped.exchange = ex

    with patch("crypto_bot.dashboard.app._make_client", return_value=client_wrapped):
        with TestClient(create_app()) as tc:
            r = tc.get("/")
    assert r.status_code == 200
    assert "Binance Spot" in r.text
