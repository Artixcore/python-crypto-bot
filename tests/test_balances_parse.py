from crypto_bot.data.balances import filtered_balance


def test_filtered_balance_unified_layout():
    ex = type("E", (), {})()
    ex.fetch_balance = lambda: {
        "BTC": {"free": 0.1, "used": 0.0, "total": 0.1},
        "SOL": {"free": 2.0, "used": 0.0, "total": 2.0},
        "USDT": {"free": 100.0, "used": 0.0, "total": 100.0},
    }
    b = filtered_balance(ex)
    assert b["BTC"]["free"] == 0.1
    assert b["USDT"]["total"] == 100.0


def test_filtered_balance_free_map_layout():
    ex = type("E", (), {})()
    ex.fetch_balance = lambda: {
        "free": {"BTC": 0.05, "SOL": 1.0, "USDT": 50.0},
        "used": {"BTC": 0.0, "SOL": 0.0, "USDT": 0.0},
        "total": {"BTC": 0.05, "SOL": 1.0, "USDT": 50.0},
    }
    b = filtered_balance(ex)
    assert b["BTC"]["free"] == 0.05
    assert b["SOL"]["total"] == 1.0
