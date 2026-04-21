import pytest

from crypto_bot.universe import TRADING_PAIRS, is_allowed_trading_pair, parse_pair_or_raise


def test_trading_pairs():
    assert TRADING_PAIRS == ("BTC/USDT", "SOL/USDT")


def test_is_allowed():
    assert is_allowed_trading_pair("BTC/USDT") is True
    assert is_allowed_trading_pair("ETH/USDT") is False


def test_parse_pair_or_raise():
    assert parse_pair_or_raise("btc/usdt") == "BTC/USDT"
    with pytest.raises(ValueError):
        parse_pair_or_raise("ETH/USDT")
