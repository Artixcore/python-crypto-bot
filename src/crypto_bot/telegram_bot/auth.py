from __future__ import annotations


def parse_allowed_user_ids(raw: str) -> set[int]:
    """Comma-separated Telegram user IDs (integers)."""
    out: set[int] = set()
    for part in raw.split(","):
        p = part.strip()
        if p.isdigit():
            out.add(int(p))
        elif p.startswith("-") and p[1:].isdigit():
            out.add(int(p))
    return out


def user_allowed(user_id: int | None, allowed: set[int]) -> bool:
    """If ``allowed`` is empty, any Telegram user may use the bot (optional restriction)."""
    if user_id is None:
        return False
    if not allowed:
        return True
    return user_id in allowed
