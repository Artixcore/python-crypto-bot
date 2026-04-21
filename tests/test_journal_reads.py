from pathlib import Path
from tempfile import TemporaryDirectory

from crypto_bot.journal.store import JournalStore


def test_recent_events_empty_db() -> None:
    with TemporaryDirectory() as d:
        j = JournalStore(Path(d) / "e.db")
        assert j.recent_events(limit=5) == []
        j.close()


def test_recent_events_filter_and_order() -> None:
    with TemporaryDirectory() as d:
        j = JournalStore(Path(d) / "e.db")
        j.write("tick", {"symbol": "BTC/USDT", "x": 1})
        j.write("risk", {"symbol": "SOL/USDT"})
        j.write("tick", {"symbol": "SOL/USDT", "x": 2})
        rows = j.recent_events(limit=10, event_eq="tick")
        assert len(rows) == 2
        assert rows[0]["payload"]["symbol"] == "SOL/USDT"
        j.close()


def test_last_tick_by_symbol() -> None:
    with TemporaryDirectory() as d:
        j = JournalStore(Path(d) / "e.db")
        j.write("tick", {"symbol": "BTC/USDT", "want_long": True})
        j.write("tick", {"symbol": "BTC/USDT", "want_long": False})
        m = j.last_tick_by_symbol(max_scan=50)
        assert m["BTC/USDT"]["want_long"] is False
        j.close()


def test_paper_sell_summary() -> None:
    with TemporaryDirectory() as d:
        j = JournalStore(Path(d) / "e.db")
        j.write("paper_sell", {"pnl": 2.0})
        j.write("paper_sell", {"pnl": -1.0})
        j.write("paper_sell", {"foo": 1})
        s = j.paper_sell_summary(limit=20)
        assert s["wins"] == 1
        assert s["losses"] == 1
        assert s["closed_with_pnl_count"] == 2
        assert s["total_pnl"] == 1.0
        j.close()


def test_event_counts() -> None:
    with TemporaryDirectory() as d:
        j = JournalStore(Path(d) / "e.db")
        for _ in range(3):
            j.write("tick", {"a": 1})
        j.write("risk", {"b": 1})
        c = j.event_counts(last_n_rows=10)
        assert c.get("tick", 0) == 3
        assert c.get("risk", 0) == 1
        j.close()
