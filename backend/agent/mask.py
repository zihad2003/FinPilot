"""PII masking applied before any text reaches the model or leaves the API."""

import re

_ACCOUNT = re.compile(r"\b\d{8,18}\b")
_ACCOUNT_GROUPED = re.compile(r"\b(?:\d[ -]?){12,18}\b")
_EMAIL = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def mask_text(text: str | None, names: list[str] | None = None) -> str:
    if not text:
        return ""
    masked = text
    for name in names or []:
        cleaned = (name or "").strip()
        if len(cleaned) < 3:
            continue
        masked = re.sub(re.escape(cleaned), "[NAME]", masked, flags=re.IGNORECASE)
    masked = _EMAIL.sub("[EMAIL]", masked)
    masked = _ACCOUNT.sub("[ACCOUNT]", masked)
    masked = _ACCOUNT_GROUPED.sub("[ACCOUNT]", masked)
    return masked


def contains_account_number(text: str) -> bool:
    return bool(_ACCOUNT.search(text or "") or _ACCOUNT_GROUPED.search(text or ""))
