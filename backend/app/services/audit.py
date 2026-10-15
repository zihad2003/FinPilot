"""Append-only audit writes. Committing here keeps the row if a later step rolls back."""

import hashlib
import json

from sqlalchemy.orm import Session

from app.clock import utcnow
from app.models import AuditLog


def input_hash(payload: dict | None) -> str:
    raw = json.dumps(payload or {}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def write_audit(
    db: Session,
    *,
    actor: str,
    tool: str,
    args: dict | None,
    outcome: str,
    result: str,
    idempotency_key: str | None = None,
    user_id: int | None = None,
    rule_id: str | None = None,
    commit: bool = True,
) -> AuditLog:
    row = AuditLog(
        timestamp=utcnow(),
        actor=actor,
        tool=tool,
        input_hash=input_hash(args),
        policy_outcome=outcome,
        result=result[:1000],
        idempotency_key=idempotency_key,
        user_id=user_id,
        rule_id=rule_id,
    )
    db.add(row)
    if commit:
        db.commit()
    else:
        db.flush()
    return row
