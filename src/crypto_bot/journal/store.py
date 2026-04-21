from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_payload(payload_json: str) -> dict[str, Any]:
    try:
        raw = json.loads(payload_json)
        return raw if isinstance(raw, dict) else {"_raw": raw}
    except json.JSONDecodeError:
        return {"_parse_error": True, "raw": payload_json[:500]}


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

    def recent_events(
        self,
        *,
        limit: int = 50,
        event_eq: str | None = None,
        event_prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Newest first. At most one of event_eq / event_prefix should be set.
        """
        q = "SELECT id, ts, event, payload_json FROM events WHERE 1=1"
        args: list[Any] = []
        if event_eq is not None:
            q += " AND event = ?"
            args.append(event_eq)
        elif event_prefix is not None:
            q += " AND event LIKE ?"
            args.append(f"{event_prefix}%")
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        cur = self._conn.execute(q, args)
        out: list[dict[str, Any]] = []
        for row in cur.fetchall():
            eid, ts, event, payload_json = row
            out.append(
                {
                    "id": eid,
                    "ts": ts,
                    "event": event,
                    "payload": _parse_payload(str(payload_json)),
                },
            )
        return out

    def last_tick_by_symbol(self, *, max_scan: int = 3000) -> dict[str, dict[str, Any]]:
        """Latest journal tick row per symbol (newest first scan)."""
        rows = self.recent_events(limit=max_scan, event_eq="tick")
        by_sym: dict[str, dict[str, Any]] = {}
        for r in rows:
            p = r["payload"]
            sym = str(p.get("symbol", ""))
            if sym and sym not in by_sym:
                by_sym[sym] = {**p, "_journal_ts": r["ts"]}
        return by_sym

    def paper_sell_summary(self, *, limit: int = 500) -> dict[str, Any]:
        """
        Aggregates closed paper trades when payload includes pnl (runner paper mode).
        Not applicable to live fills unless journal is extended.
        """
        rows = self.recent_events(limit=limit, event_eq="paper_sell")
        wins = 0
        losses = 0
        total_pnl = 0.0
        for r in rows:
            pnl = r["payload"].get("pnl")
            if pnl is None:
                continue
            try:
                v = float(pnl)
            except (TypeError, ValueError):
                continue
            total_pnl += v
            if v > 0:
                wins += 1
            elif v < 0:
                losses += 1
        n = wins + losses
        win_rate_pct = (wins / n * 100.0) if n else 0.0
        return {
            "wins": wins,
            "losses": losses,
            "total_pnl": total_pnl,
            "win_rate_pct": win_rate_pct,
            "closed_with_pnl_count": n,
        }

    def event_counts(self, *, last_n_rows: int = 1000) -> dict[str, int]:
        """Event name frequencies over the last N rows (by id)."""
        cur = self._conn.execute(
            """
            SELECT event, COUNT(*) FROM (
                SELECT event FROM events ORDER BY id DESC LIMIT ?
            ) AS tail GROUP BY event
            """,
            (last_n_rows,),
        )
        return {str(k): int(v) for k, v in cur.fetchall()}
