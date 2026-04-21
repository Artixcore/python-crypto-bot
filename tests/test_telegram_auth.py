from crypto_bot.telegram_bot.auth import parse_allowed_user_ids, user_allowed


def test_parse_allowed_user_ids():
    s = parse_allowed_user_ids("123, 456 , , 789")
    assert s == {123, 456, 789}


def test_user_allowed():
    allowed = {42, 99}
    assert user_allowed(42, allowed) is True
    assert user_allowed(1, allowed) is False
    assert user_allowed(None, allowed) is False


def test_empty_allowlist_allows_any_user():
    """Unset CRYPTO_BOT_TELEGRAM_ALLOWED_USER_IDS means no restriction."""
    assert user_allowed(1, set()) is True
    assert user_allowed(999, set()) is True
