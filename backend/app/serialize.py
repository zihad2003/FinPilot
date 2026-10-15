"""API serializers. Account numbers are masked before they leave the server."""

from agent.mask import mask_text
from app.models import Account, AuditLog, Goal, Proposal, Transaction, User
from insights.service import goal_views


def user_public(user: User, account: Account | None) -> dict:
    masked = None
    if account and account.account_number:
        tail = account.account_number[-4:]
        masked = f"****{tail}"
    return {
        "id": user.id,
        "name": user.name,
        "currency": user.currency,
        "income_monthly": user.income_monthly,
        "risk_notes": user.risk_notes,
        "account_number_masked": masked,
    }


def account_public(account: Account) -> dict:
    tail = account.account_number[-4:] if account.account_number else ""
    return {
        "id": account.id,
        "user_id": account.user_id,
        "type": account.type,
        "name": account.name,
        "balance": round(account.balance, 2),
        "currency": account.currency,
        "account_number_masked": f"****{tail}" if tail else None,
    }


def transaction_public(txn: Transaction, names: list[str]) -> dict:
    return {
        "id": txn.id,
        "account_id": txn.account_id,
        "date": txn.date.isoformat(),
        "amount": round(txn.amount, 2),
        "merchant": mask_text(txn.merchant, names),
        "raw_description": mask_text(txn.raw_description, names),
        "category": txn.category,
        "confidence": txn.confidence,
        "source": txn.source,
        "currency": txn.currency,
    }


def proposal_public(proposal: Proposal) -> dict:
    return {
        "id": proposal.id,
        "user_id": proposal.user_id,
        "action_type": proposal.action_type,
        "payload": proposal.payload,
        "reason": proposal.reason,
        "evidence_ids": proposal.evidence_ids or [],
        "status": proposal.status,
        "expires_at": proposal.expires_at.isoformat() + "Z",
        "rule_id": proposal.rule_id,
        "expected_effect": proposal.expected_effect,
        "created_at": proposal.created_at.isoformat() + "Z",
    }


def audit_public(row: AuditLog) -> dict:
    return {
        "id": row.id,
        "timestamp": row.timestamp.isoformat() + "Z",
        "actor": row.actor,
        "tool": row.tool,
        "input_hash": row.input_hash,
        "policy_outcome": row.policy_outcome,
        "result": row.result,
        "idempotency_key": row.idempotency_key,
        "rule_id": row.rule_id,
        "user_id": row.user_id,
    }


def goals_public(db, user_id: int) -> list[dict]:
    return goal_views(db, user_id)
