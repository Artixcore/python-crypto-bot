"""Failure injection: order router surfaces exchange errors."""

from unittest.mock import patch

import pytest

from crypto_bot.data.binance_client import BinanceSpotClient
from crypto_bot.execution.order_router import OrderRequest, OrderRouter


def test_order_router_propagates_error():
    client = BinanceSpotClient()
    router = OrderRouter(client)
    req = OrderRequest(symbol="BTC/USDT", side="buy", type="market", amount=0.001)
    with patch.object(
        client.exchange,
        "create_order",
        side_effect=Exception("network down"),
    ):
        with pytest.raises(Exception, match="network down"):
            router.place(req)
