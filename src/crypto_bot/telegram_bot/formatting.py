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
