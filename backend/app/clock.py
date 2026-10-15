"""Clock used by policy expiry. Tests replace Clock.now."""

from datetime import datetime, timezone


class Clock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)


clock = Clock()


def utcnow() -> datetime:
    return clock.now()
