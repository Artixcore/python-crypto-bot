from crypto_bot.config.settings import AppSettings, TradingProfile
from crypto_bot.journal.store import JournalStore
from crypto_bot.telegram_bot.views import (
    format_hub_html,
    format_help_html,
    format_strategy_risk_html,
)


def test_format_hub_html_includes_profile() -> None:
    settings = AppSettings(profile=TradingProfile.PAPER)
    snap = {
        "balance": {"USDT": {"free": 100.0, "total": 100.0}},
        "tickers": {"BTC/USDT": {"last": 50_000.0}},
        "meta": {"fetched_at": "2026-01-01T00:00:00+00:00", "error": None},
    }
    html = format_hub_html(settings, snap)
    assert "paper" in html
    assert "Portfolio equity" in html


def test_format_help_html() -> None:
    h = format_help_html()
    assert "/start" in h
    assert "<b>" in h


def test_format_strategy_risk_journal(tmp_path) -> None:
    j = JournalStore(tmp_path / "j.db")
    try:
        settings = AppSettings()
        html = format_strategy_risk_html(settings, j)
        assert "Strategy" in html
        assert "Kill switch" in html
    finally:
        j.close()
