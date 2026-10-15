"""HTTP routes for the sandbox bank, insights, and chat."""

import csv
import io
from datetime import date as Date

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agent.categorize import CATEGORIES, remember_correction
from agent.llm import LLMClient, build_llm_from_settings
from agent.loop import run_chat
from app.db import get_db
from app.models import Account, AuditLog, Goal, Permission, Proposal, Transaction, User
from app.rate_limit import check_rate
from app.serialize import account_public, audit_public, proposal_public, transaction_public, user_public
from app.services.bank import (
    BankError,
    approve_proposal,
    checking_account,
    edit_proposal,
    reject_proposal,
    request_money_movement,
    user_names,
)
from insights.service import budget_status, detect_anomalies, generate_budget, goal_views, refresh_recurring, simulate_scenario

router = APIRouter()
CSV_LIMIT = 1_000_000


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: float = Field(gt=0, le=1_000_000)
    target_date: Date
    current_amount: float = 0


class BillIn(BaseModel):
    payee: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    date: Date | None = None
    note: str | None = Field(default=None, max_length=500)
    user_id: int = 1


class TransferIn(BaseModel):
    goal_id: int
    amount: float = Field(gt=0)
    user_id: int = 1


class PermissionIn(BaseModel):
    tier: str = Field(pattern="^T[0-3]$")
    per_action_limit: float | None = Field(default=None, ge=0)
    daily_limit: float | None = Field(default=None, ge=0)


class CategoryIn(BaseModel):
    category: str


class ProposalEdit(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    payee: str | None = None
    date: Date | None = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    user_id: int = 1


class ScenarioChange(BaseModel):
    op: str
    merchant: str | None = None
    category: str | None = None
    amount: float | None = None


class ScenarioIn(BaseModel):
    changes: list[ScenarioChange]
    user_id: int = 1


def get_llm() -> LLMClient:
    return build_llm_from_settings()


def _names(db: Session, user_id: int) -> list[str]:
    return user_names(db, user_id)


@router.get("/")
def root():
    return {
        "name": "FinPilot",
        "sandbox": True,
        "notice": "Sandbox only. Not real money and not regulated financial advice.",
    }


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/me")
def me(user_id: int = 1, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User was not found.")
    account = db.query(Account).filter(Account.user_id == user_id, Account.type == "checking").one_or_none()
    return user_public(user, account)


@router.get("/accounts")
def list_accounts(user_id: int = 1, db: Session = Depends(get_db)):
    rows = db.query(Account).filter(Account.user_id == user_id).all()
    return [account_public(row) for row in rows]


@router.get("/transactions")
def list_transactions(
    user_id: int = 1,
    date_from: Date | None = None,
    date_to: Date | None = None,
    category: str | None = None,
    merchant: str | None = None,
    limit: int = Query(default=200, le=500),
    db: Session = Depends(get_db),
):
    account_ids = [row.id for row in db.query(Account.id).filter(Account.user_id == user_id).all()]
    query = db.query(Transaction).filter(Transaction.account_id.in_(account_ids or [-1]))
    if date_from:
        query = query.filter(Transaction.date >= date_from)
    if date_to:
        query = query.filter(Transaction.date <= date_to)
    if category:
        query = query.filter(Transaction.category == category)
    if merchant:
        query = query.filter(Transaction.merchant.ilike(f"%{merchant}%"))
    rows = query.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).all()
    names = _names(db, user_id)
    return [transaction_public(row, names) for row in rows]


@router.post("/transactions/import")
async def import_csv(
    file: UploadFile = File(...),
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(400, "Upload a .csv file.")
    raw = await file.read()
    if len(raw) > CSV_LIMIT:
        raise HTTPException(400, "CSV is larger than 1 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must be UTF-8 text.")
    reader = csv.DictReader(io.StringIO(text))
    fields = {name.strip().lower() for name in (reader.fieldnames or [])}
    if not {"date", "description", "amount"}.issubset(fields):
        raise HTTPException(400, "CSV needs date, description, and amount columns.")
    account = checking_account(db, user_id)
    created = []
    for index, row in enumerate(reader):
        if index >= 2000:
            break
        normalized = {str(key).strip().lower(): (value or "").strip() for key, value in row.items() if key}
        description = normalized.get("description") or ""
        if description.startswith("="):
            description = description[1:]
        try:
            when = Date.fromisoformat(normalized.get("date", "")[:10])
            amount = round(float(normalized.get("amount") or "nan"), 2)
        except ValueError:
            continue
        from agent.categorize import categorize_merchant

        category, confidence, source = categorize_merchant(db, user_id, description)
        txn = Transaction(
            account_id=account.id,
            date=when,
            amount=amount,
            merchant=description[:200],
            raw_description=description,
            category=category,
            confidence=confidence,
            source=source,
            currency=(normalized.get("currency") or "USD")[:8],
        )
        db.add(txn)
        account.balance = round(account.balance + amount, 2)
        created.append(txn)
    from app.services.audit import write_audit

    write_audit(
        db,
        actor="user",
        tool="csv_import",
        args={"rows": len(created)},
        outcome="ALLOW",
        result="stored CSV rows as data, not instructions",
        user_id=user_id,
        rule_id="DATA_NOT_INSTRUCTIONS",
        commit=False,
    )
    db.commit()
    names = _names(db, user_id)
    return {"imported": len(created), "transactions": [transaction_public(txn, names) for txn in created]}


@router.patch("/transactions/{transaction_id}/category")
def correct_category(transaction_id: int, body: CategoryIn, user_id: int = 1, db: Session = Depends(get_db)):
    if body.category not in CATEGORIES:
        raise HTTPException(400, "Unknown category.")
    txn = db.get(Transaction, transaction_id)
    account_ids = [row.id for row in db.query(Account.id).filter(Account.user_id == user_id).all()]
    if txn is None or txn.account_id not in account_ids:
        raise HTTPException(404, "Transaction was not found.")
    remember_correction(db, user_id, txn.merchant, body.category)
    db.refresh(txn)
    return transaction_public(txn, _names(db, user_id))


@router.post("/bills/schedule")
def schedule_bill(
    body: BillIn,
    db: Session = Depends(get_db),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    outcome = request_money_movement(
        db,
        user_id=body.user_id,
        tool_name="schedule_bill",
        args={"payee": body.payee, "amount": body.amount, "date": body.date, "note": body.note},
        idempotency_key=idempotency_key,
        actor="user",
    )
    return _movement_response(outcome)


@router.post("/transfers")
def transfer(
    body: TransferIn,
    db: Session = Depends(get_db),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    outcome = request_money_movement(
        db,
        user_id=body.user_id,
        tool_name="transfer_to_goal",
        args={"goal_id": body.goal_id, "amount": body.amount},
        idempotency_key=idempotency_key,
        actor="user",
    )
    return _movement_response(outcome)


@router.get("/goals")
def list_goals(user_id: int = 1, db: Session = Depends(get_db)):
    return goal_views(db, user_id)


@router.post("/goals")
def create_goal(body: GoalIn, user_id: int = 1, db: Session = Depends(get_db)):
    goal = Goal(
        user_id=user_id,
        name=body.name,
        target_amount=body.target_amount,
        target_date=body.target_date,
        current_amount=body.current_amount,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal_views(db, user_id)


@router.get("/permissions")
def list_permissions(user_id: int = 1, db: Session = Depends(get_db)):
    rows = db.query(Permission).filter(Permission.user_id == user_id).order_by(Permission.action_type).all()
    return [
        {
            "id": row.id,
            "action_type": row.action_type,
            "tier": row.tier,
            "per_action_limit": row.per_action_limit,
            "daily_limit": row.daily_limit,
        }
        for row in rows
    ]


@router.patch("/permissions/{action_type}")
def update_permission(action_type: str, body: PermissionIn, user_id: int = 1, db: Session = Depends(get_db)):
    row = (
        db.query(Permission)
        .filter(Permission.user_id == user_id, Permission.action_type == action_type)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Permission was not found.")
    row.tier = body.tier
    row.per_action_limit = body.per_action_limit
    row.daily_limit = body.daily_limit
    db.commit()
    return {
        "action_type": row.action_type,
        "tier": row.tier,
        "per_action_limit": row.per_action_limit,
        "daily_limit": row.daily_limit,
    }


@router.get("/proposals")
def list_proposals(user_id: int = 1, status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Proposal).filter(Proposal.user_id == user_id)
    if status:
        query = query.filter(Proposal.status == status)
    rows = query.order_by(Proposal.id.desc()).all()
    return [proposal_public(row) for row in rows]


@router.patch("/proposals/{proposal_id}")
def patch_proposal(proposal_id: int, body: ProposalEdit, user_id: int = 1, db: Session = Depends(get_db)):
    proposal = edit_proposal(db, user_id, proposal_id, body.model_dump(exclude_none=True))
    return proposal_public(proposal)


@router.post("/proposals/{proposal_id}/approve")
def approve(
    proposal_id: int,
    user_id: int = 1,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    outcome = approve_proposal(db, user_id, proposal_id, idempotency_key)
    return _movement_response(outcome)


@router.post("/proposals/{proposal_id}/reject")
def reject(proposal_id: int, user_id: int = 1, db: Session = Depends(get_db)):
    proposal = reject_proposal(db, user_id, proposal_id)
    return proposal_public(proposal)


@router.get("/audit")
def list_audit(
    user_id: int = 1,
    policy_outcome: str | None = None,
    tool: str | None = None,
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog).filter(AuditLog.user_id == user_id)
    if policy_outcome:
        query = query.filter(AuditLog.policy_outcome == policy_outcome)
    if tool:
        query = query.filter(AuditLog.tool == tool)
    rows = query.order_by(AuditLog.id.desc()).limit(limit).all()
    return [audit_public(row) for row in rows]


@router.get("/audit/export")
def export_audit(
    user_id: int = 1,
    policy_outcome: str | None = None,
    db: Session = Depends(get_db),
):
    from fastapi.responses import Response

    query = db.query(AuditLog).filter(AuditLog.user_id == user_id)
    if policy_outcome:
        query = query.filter(AuditLog.policy_outcome == policy_outcome)
    rows = query.order_by(AuditLog.id.asc()).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "timestamp", "actor", "tool", "input_hash", "policy_outcome", "result", "idempotency_key", "rule_id"]
    )
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.timestamp.isoformat(),
                row.actor,
                row.tool,
                row.input_hash,
                row.policy_outcome,
                row.result,
                row.idempotency_key or "",
                row.rule_id or "",
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=finpilot-audit.csv"},
    )


@router.get("/insights/budget")
def get_budget(month: str = "2026-10", user_id: int = 1, db: Session = Depends(get_db)):
    return budget_status(db, user_id, month)


@router.post("/insights/budget/generate")
def post_budget(month: str = "2026-10", user_id: int = 1, db: Session = Depends(get_db)):
    return generate_budget(db, user_id, month)


@router.get("/insights/recurring")
def get_recurring(user_id: int = 1, db: Session = Depends(get_db)):
    return {"recurring": refresh_recurring(db, user_id)}


@router.get("/insights/anomalies")
def get_anomalies(month: str | None = None, user_id: int = 1, db: Session = Depends(get_db)):
    return {"anomalies": detect_anomalies(db, user_id, month)}


@router.get("/insights/goals")
def get_goal_insights(user_id: int = 1, db: Session = Depends(get_db)):
    return {"goals": goal_views(db, user_id)}


@router.post("/insights/simulate")
def post_simulate(body: ScenarioIn, db: Session = Depends(get_db)):
    before_balance = checking_account(db, body.user_id).balance
    result = simulate_scenario(db, body.user_id, [change.model_dump() for change in body.changes])
    after_balance = checking_account(db, body.user_id).balance
    result["balance_unchanged"] = before_balance == after_balance
    return result


@router.get("/insights/summary")
def summary(month: str = "2026-10", user_id: int = 1, db: Session = Depends(get_db)):
    account = checking_account(db, user_id)
    names = _names(db, user_id)
    recent = (
        db.query(Transaction)
        .filter(Transaction.account_id == account.id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(12)
        .all()
    )
    actions = (
        db.query(AuditLog).filter(AuditLog.user_id == user_id).order_by(AuditLog.id.desc()).limit(8).all()
    )
    return {
        "account": account_public(account),
        "budget": budget_status(db, user_id, month),
        "goals": goal_views(db, user_id),
        "anomalies": detect_anomalies(db, user_id, month),
        "recent_transactions": [transaction_public(row, names) for row in recent],
        "recent_actions": [audit_public(row) for row in actions],
    }


@router.post("/chat")
def chat(
    body: ChatIn,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    check_rate(f"user:{body.user_id}")
    return run_chat(db, body.user_id, body.message, llm)


def _movement_response(outcome: dict) -> dict:
    proposal = outcome.get("proposal")
    if outcome["outcome"] == "DENY" and not outcome.get("executed"):
        raise BankError(403, outcome["reason"], outcome["rule_id"])
    return {
        "outcome": outcome["outcome"],
        "rule_id": outcome["rule_id"],
        "reason": outcome["reason"],
        "tier": outcome.get("tier"),
        "executed": outcome.get("executed", False),
        "result": outcome.get("result"),
        "proposal": proposal_public(proposal) if proposal is not None else None,
    }
