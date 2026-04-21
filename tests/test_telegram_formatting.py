from crypto_bot.telegram_bot.formatting import split_telegram_chunks


def test_split_long_message():
    text = "a" * 5000
    parts = split_telegram_chunks(text, max_len=4096)
    assert len(parts) == 2
    assert len(parts[0]) == 4096
    assert len(parts[1]) == 904
