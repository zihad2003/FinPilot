"""Sandbox money movement. Policy decides; this module only applies an allowed action."""

import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from agent.categorize import categorize_merchant, merchant_key
from app.clock import utcnow
from app.models import Account, Goal, IdempotencyRecord, MoneyMovement, Proposal, Transaction, User
from app.services.audit import write_audit
from policy.engine import MONEY_TOOLS, PolicyEngine


class BankError(Exception):
    def __init__(self, status_code: int, detail: str, code: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


def money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def checking_account(db: Session, user_id: int) -> Account:
    account = (
        db.query(Account)
        .filter(Account.user_id == user_id, Account.type == "checking")
        .one_or_none()
    )
    if account is None:
        raise BankError(404, "Checking account was not found.", "account_not_found")
    return account


def _existing_key(db: Session, key: str) -> IdempotencyRecord | None:
    return db.query(IdempotencyRecord).filter(IdempotencyRecord.key == key).one_or_none()


def expected_effect(db: Session, user_id: int, amount: float, goal_id: int | None = None) -> str:
    account = checking_account(db, user_id)
    after = money(account.balance - amount)
    text = f"Checking balance {account.balance:.2f} would become {after:.2f}."
    if goal_id:
        goal = db.get(Goal, int(goal_id))
        if goal and goal.user_id == user_id:
            text += f" {goal.name} would rise from {goal.current_amount:.2f} to {money(goal.current_amount + amount):.2f}."
    return text


def evidence_for(db: Session, user_id: int, payee: str | None) -> list[int]:
    if not payee:
        return []
    account = checking_account(db, user_id)
    rows = db.query(Transaction).filter(Transaction.account_id == account.id).all()
    matched = [row for row in rows if merchant_key(payee) and merchant_key(payee) in merchant_key(row.merchant)]
    matched.sort(key=lambda row: row.date, reverse=True)
    return [row.id for row in matched[:5]]


def server_reason(action_type: str, payload: dict, db: Session) -> str:
    amount = float(payload.get("amount") or 0)
    if action_type == "schedule_bill":
        payee = payload.get("payee") or "the payee"
        when = payload.get("date") or "today"
        return f"Pay {payee} {amount:.2f} on {when}. The amount is taken from the request, not from text in a description."
    goal = db.get(Goal, int(payload.get("goal_id") or 0)) if payload.get("goal_id") else None
    name = goal.name if goal else "the savings goal"
    return f"Move {amount:.2f} into {name}."


def _clean_note(note: str | None) -> str:
    if not note:
        return ""
    lowered = note.lower()
    if "ignore previous" in lowered or "transfer all" in lowered:
        return ""
    return note.strip()[:500]


def save_proposal(
    db: Session,
    *,
    user_id: int,
    action_type: str,
    payload: dict,
    reason: str,
    evidence_ids: list[int],
    status: str,
    rule_id: str,
    expected_effect_text: str,
    idempotency_key: str | None,
) -> Proposal:
    if idempotency_key and _existing_key(db, idempotency_key):
        write_audit(
            db,
            actor="agent",
            tool=action_type,
            args=payload,
            outcome="DENY",
            result="duplicate idempotency key on proposal",
            idempotency_key=idempotency_key,
            user_id=user_id,
            rule_id="DUPLICATE_IDEMPOTENCY",
        )
        raise BankError(409, "Duplicate idempotency key.", "duplicate_idempotency_key")
    now = utcnow()
    proposal = Proposal(
        user_id=user_id,
        action_type=action_type,
        payload=payload,
        reason=reason,
        evidence_ids=evidence_ids,
        status=status,
        expires_at=now + timedelta(minutes=15),
        rule_id=rule_id,
        expected_effect=expected_effect_text,
        idempotency_key=idempotency_key,
        created_at=now,
    )
    db.add(proposal)
    if idempotency_key:
        db.add(
            IdempotencyRecord(
                key=idempotency_key,
                user_id=user_id,
                endpoint=f"proposal:{action_type}",
                created_at=now,
            )
        )
    db.commit()
    db.refresh(proposal)
    return proposal


def apply_movement(
    db: Session,
    *,
    user_id: int,
    action_type: str,
    amount: float,
    idempotency_key: str,
    payee: str | None = None,
    goal_id: int | None = None,
    when: date | None = None,
    note: str | None = None,
    actor: str = "agent",
) -> dict:
    if not idempotency_key:
        raise BankError(400, "Idempotency-Key is required.", "missing_idempotency_key")
    if _existing_key(db, idempotency_key):
        write_audit(
            db,
            actor=actor,
            tool=action_type,
            args={"amount": amount, "payee": payee, "goal_id": goal_id},
            outcome="DENY",
            result="duplicate execution rejected",
            idempotency_key=idempotency_key,
            user_id=user_id,
            rule_id="DUPLICATE_IDEMPOTENCY",
        )
        raise BankError(409, "Duplicate idempotency key.", "duplicate_idempotency_key")

    account = checking_account(db, user_id)
    amount = money(amount)
    if account.balance + 1e-9 < amount:
        write_audit(
            db,
            actor=actor,
            tool=action_type,
            args={"amount": amount},
            outcome="DENY",
            result="insufficient sandbox balance",
            idempotency_key=idempotency_key,
            user_id=user_id,
            rule_id="INSUFFICIENT_FUNDS",
        )
        raise BankError(422, "Insufficient sandbox balance.", "insufficient_funds")

    goal = None
    if action_type == "transfer_to_goal":
        goal = db.get(Goal, int(goal_id or 0))
        if goal is None or goal.user_id != user_id:
            raise BankError(404, "Goal was not found.", "goal_not_found")

    account.balance = money(account.balance - amount)
    when = when or utcnow().date()
    if action_type == "transfer_to_goal" and goal is not None:
        goal.current_amount = money(goal.current_amount + amount)
        merchant = f"GOAL {goal.name}"
        description = f"Transfer to {goal.name}"
        category, confidence, source = "savings", 0.99, "rule"
    else:
        merchant = payee or "Bill payment"
        description = note or f"Bill payment to {merchant}"
        category, confidence, source = categorize_merchant(db, user_id, merchant)

    txn = Transaction(
        account_id=account.id,
        date=when,
        amount=-amount,
        merchant=merchant,
        raw_description=description,
        category=category,
        confidence=confidence,
        source=source,
        currency=account.currency,
    )
    db.add(txn)
    db.flush()
    now = utcnow()
    db.add(
        IdempotencyRecord(
            key=idempotency_key,
            user_id=user_id,
            endpoint=action_type,
            created_at=now,
        )
    )
    db.add(
        MoneyMovement(
            user_id=user_id,
            action_type=action_type,
            amount=amount,
            payee=payee,
            idempotency_key=idempotency_key,
            created_at=now,
            goal_id=goal.id if goal else None,
        )
    )
    write_audit(
        db,
        actor=actor,
        tool=action_type,
        args={"amount": amount, "payee": payee, "goal_id": goal_id},
        outcome="ALLOW",
        result=f"executed transaction {txn.id}",
        idempotency_key=idempotency_key,
        user_id=user_id,
        rule_id="EXECUTED",
        commit=False,
    )
    db.commit()
    db.refresh(account)
    return {
        "executed": True,
        "transaction_id": txn.id,
        "balance": account.balance,
        "goal_id": goal.id if goal else None,
        "goal_balance": goal.current_amount if goal else None,
    }


def request_money_movement(
    db: Session,
    *,
    user_id: int,
    tool_name: str,
    args: dict,
    idempotency_key: str | None,
    actor: str = "agent",
    approved: bool = False,
) -> dict:
    if tool_name not in MONEY_TOOLS:
        raise BankError(400, "Not a money movement.", "not_money_tool")
    payload = {
        "payee": args.get("payee"),
        "amount": args.get("amount"),
        "date": str(args.get("date") or utcnow().date()),
        "goal_id": args.get("goal_id"),
        "note": args.get("note"),
    }
    engine = PolicyEngine(db)
    decision = engine.evaluate(
        user_id,
        tool_name,
        args,
        actor=actor,
        approved=approved,
        idempotency_key=idempotency_key,
    )
    base = {
        "outcome": decision.outcome,
        "rule_id": decision.rule_id,
        "reason": decision.reason,
        "tier": decision.tier,
        "executed": False,
        "proposal": None,
        "result": None,
    }
    if decision.outcome == "DENY" and decision.rule_id == "T0_READONLY":
        proposal = save_proposal(
            db,
            user_id=user_id,
            action_type=tool_name,
            payload=payload,
            reason=decision.reason + " A blocked card was filed so you can see the request.",
            evidence_ids=evidence_for(db, user_id, payload.get("payee")),
            status="blocked",
            rule_id=decision.rule_id,
            expected_effect_text=expected_effect(db, user_id, float(args.get("amount") or 0), args.get("goal_id")),
            idempotency_key=idempotency_key,
        )
        base["proposal"] = proposal
        return base
    if decision.outcome == "DENY":
        return base
    if decision.outcome == "REQUIRE_APPROVAL":
        status = "proposed" if decision.rule_id == "T1_PROPOSE_ONLY" else "pending"
        note = _clean_note(args.get("reason") or args.get("note"))
        reason = server_reason(tool_name, payload, db)
        if note:
            reason = f"{reason} Agent note: {note}"
        proposal = save_proposal(
            db,
            user_id=user_id,
            action_type=tool_name,
            payload=payload,
            reason=reason,
            evidence_ids=evidence_for(db, user_id, payload.get("payee") or ""),
            status=status,
            rule_id=decision.rule_id,
            expected_effect_text=expected_effect(
                db, user_id, float(args.get("amount") or 0), payload.get("goal_id")
            ),
            idempotency_key=idempotency_key,
        )
        base["proposal"] = proposal
        return base

    key = idempotency_key or f"auto-{uuid.uuid4()}"
    when = _parse_date(args.get("date"))
    result = apply_movement(
        db,
        user_id=user_id,
        action_type=tool_name,
        amount=float(args["amount"]),
        idempotency_key=key,
        payee=args.get("payee"),
        goal_id=int(args["goal_id"]) if args.get("goal_id") else None,
        when=when,
        note=args.get("note"),
        actor=actor,
    )
    base["executed"] = True
    base["result"] = result
    return base


def approve_proposal(db: Session, user_id: int, proposal_id: int, idempotency_key: str | None) -> dict:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None or proposal.user_id != user_id:
        raise BankError(404, "Proposal was not found.", "proposal_not_found")
    key = idempotency_key or f"exec-{proposal.id}"
    execution_key = f"exec-{proposal.id}"
    if proposal.status == "executed" or _existing_key(db, execution_key):
        write_audit(
            db,
            actor="user",
            tool=proposal.action_type,
            args=proposal.payload or {},
            outcome="DENY",
            result="duplicate execution rejected",
            idempotency_key=key,
            user_id=user_id,
            rule_id="DUPLICATE_IDEMPOTENCY",
        )
        raise BankError(409, "This action was already executed.", "duplicate_idempotency_key")
    if proposal.status != "pending":
        raise BankError(409, f"This proposal is {proposal.status} and cannot be executed.", "not_executable")
    if proposal.expires_at <= utcnow():
        proposal.status = "expired"
        write_audit(
            db,
            actor="user",
            tool=proposal.action_type,
            args=proposal.payload or {},
            outcome="DENY",
            result="approval expired; nothing executed",
            idempotency_key=key,
            user_id=user_id,
            rule_id="APPROVAL_EXPIRED",
            commit=False,
        )
        db.commit()
        raise BankError(410, "This approval expired. Nothing was executed.", "proposal_expired")

    args = dict(proposal.payload or {})
    outcome = request_money_movement(
        db,
        user_id=user_id,
        tool_name=proposal.action_type,
        args=args,
        idempotency_key=f"exec-{proposal.id}",
        actor="user",
        approved=True,
    )
    if not outcome["executed"]:
        raise BankError(403, outcome["reason"], outcome["rule_id"])
    proposal.status = "executed"
    db.commit()
    outcome["proposal"] = proposal
    return outcome


def reject_proposal(db: Session, user_id: int, proposal_id: int) -> Proposal:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None or proposal.user_id != user_id:
        raise BankError(404, "Proposal was not found.", "proposal_not_found")
    if proposal.status in {"executed", "rejected", "expired"}:
        raise BankError(409, f"This proposal is already {proposal.status}.", "not_rejectable")
    proposal.status = "rejected"
    write_audit(
        db,
        actor="user",
        tool=proposal.action_type,
        args=proposal.payload or {},
        outcome="DENY",
        result="user rejected the proposal",
        user_id=user_id,
        rule_id="USER_REJECTED",
        commit=False,
    )
    db.commit()
    return proposal


def edit_proposal(db: Session, user_id: int, proposal_id: int, updates: dict) -> Proposal:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None or proposal.user_id != user_id:
        raise BankError(404, "Proposal was not found.", "proposal_not_found")
    if proposal.status != "pending":
        raise BankError(409, "Only a pending proposal can be edited.", "not_editable")
    if proposal.expires_at <= utcnow():
        proposal.status = "expired"
        db.commit()
        raise BankError(410, "This approval expired.", "proposal_expired")
    payload = dict(proposal.payload or {})
    if updates.get("amount") is not None:
        payload["amount"] = float(updates["amount"])
    if updates.get("payee"):
        payload["payee"] = updates["payee"]
    if updates.get("date"):
        payload["date"] = str(updates["date"])
    proposal.payload = payload
    proposal.expected_effect = expected_effect(
        db, user_id, float(payload.get("amount") or 0), payload.get("goal_id")
    )
    proposal.reason = server_reason(proposal.action_type, payload, db)
    db.commit()
    db.refresh(proposal)
    return proposal


def create_named_proposal(
    db: Session,
    *,
    user_id: int,
    action: str,
    reason: str,
    payload: dict,
    evidence_ids: list[int] | None,
    idempotency_key: str | None,
) -> Proposal:
    if action not in MONEY_TOOLS | {"set_budget"}:
        raise BankError(400, "Unsupported proposal action.", "bad_action")
    from app.models import Permission

    perm = (
        db.query(Permission)
        .filter(Permission.user_id == user_id, Permission.action_type == action)
        .one_or_none()
    )
    tier = perm.tier if perm else "T0"
    if action == "set_budget":
        status = "pending" if tier != "T0" else "blocked"
        rule = "PROPOSAL_DRAFT"
    elif tier == "T0":
        status, rule = "blocked", "T0_READONLY"
    elif tier == "T1":
        status, rule = "proposed", "T1_PROPOSE_ONLY"
    else:
        status, rule = "pending", "T2_REQUIRE_APPROVAL"
    clean = _clean_note(reason) or server_reason(action, payload, db)
    return save_proposal(
        db,
        user_id=user_id,
        action_type=action,
        payload=payload,
        reason=clean,
        evidence_ids=evidence_ids or evidence_for(db, user_id, payload.get("payee")),
        status=status,
        rule_id=rule,
        expected_effect_text=expected_effect(db, user_id, float(payload.get("amount") or 0), payload.get("goal_id")),
        idempotency_key=idempotency_key,
    )


def _parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def user_names(db: Session, user_id: int) -> list[str]:
    user = db.get(User, user_id)
    return [user.name] if user and user.name else []
