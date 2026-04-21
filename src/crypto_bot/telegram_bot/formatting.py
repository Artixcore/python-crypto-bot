from __future__ import annotations

import json
from typing import Any


def split_telegram_chunks(text: str, max_len: int = 4096) -> list[str]:
    """Telegram message length limit (default 4096)."""
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


def snapshot_to_messages(snapshot: dict[str, Any]) -> list[str]:
    text = json.dumps(snapshot, indent=2, ensure_ascii=False, default=str)
    return split_telegram_chunks(text)


def format_balance_table(bal: dict[str, Any]) -> str:
    lines = ["Asset | free | total", "------|------|------"]
    for asset in ("BTC", "SOL", "USDT"):
        row = bal.get(asset) or {}
        if isinstance(row, dict):
            free = row.get("free", "—")
            total = row.get("total", "—")
        else:
            free, total = "—", "—"
        lines.append(f"{asset} | {free} | {total}")
    return "\n".join(lines)


def format_status_slim(snap: dict[str, Any]) -> str:
    """Short text summary for /snapshot."""
    lines = []
    meta = snap.get("meta") or {}
    lines.append(f"fetched: {meta.get('fetched_at', '—')}")
    if meta.get("error"):
        lines.append(f"errors: {meta['error']}")
    tickers = snap.get("tickers") or {}
    for sym, t in tickers.items():
        if isinstance(t, dict):
            last = t.get("last", "—")
            lines.append(f"{sym} last={last}")
    oo = snap.get("open_orders")
    n = len(oo) if isinstance(oo, list) else 0
    lines.append(f"open_orders: {n}")
    return "\n".join(lines)
