from crypto_bot.telegram_bot.keyboards import parse_menu_callback


def test_parse_menu_callback() -> None:
    assert parse_menu_callback(None) is None
    assert parse_menu_callback("bad") is None
    assert parse_menu_callback("v:") == ""
    assert parse_menu_callback("v:hub") == "hub"
    assert parse_menu_callback("v:acct") == "acct"
