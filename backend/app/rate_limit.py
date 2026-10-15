"""In-memory chat rate limit."""

import time

from fastapi import HTTPException

from app.config import settings

_hits: dict[str, list[float]] = {}


def reset_rate_limit() -> None:
    _hits.clear()


def check_rate(key: str) -> None:
    now = time.monotonic()
    window = settings.chat_rate_window_seconds
    recent = [stamp for stamp in _hits.get(key, []) if now - stamp < window]
    if len(recent) >= settings.chat_rate_limit:
        _hits[key] = recent
        raise HTTPException(status_code=429, detail="Too many chat requests. Please wait a moment.")
    recent.append(now)
    _hits[key] = recent
