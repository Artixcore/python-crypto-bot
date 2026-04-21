from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JournalStore:
    """Append-only event log for audit and monitoring."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                event TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def write(self, event: str, payload: dict[str, Any]) -> None:
        ts = datetime.now(UTC).isoformat()
        self._conn.execute(
            "INSERT INTO events (ts, event, payload_json) VALUES (?, ?, ?)",
            (ts, event, json.dumps(payload, default=str)),
        )
        self._conn.commit()
