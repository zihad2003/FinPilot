"""Deterministic policy. The model cannot change tiers, limits, or this code."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from agent.categorize import merchant_key
from app.clock import utcnow
from app.models import MoneyMovement, PayeeAllowlist, Permission
from app.services.audit import write_audit

READ_TOOLS = {"get_transactions", "get_budget_status", "detect_recurring", "simulate_scenario"}
MONEY_TOOLS = {"schedule_bill", "transfer_to_goal"}
KNOWN_TOOLS = READ_TOOLS | MONEY_TOOLS | {"categorize", "set_budget", "create_proposal"}
SYSTEM_MAX_AMOUNT = 20_000.0


@dataclass
class PolicyDecision:
    outcome: str
    reason: str
    rule_id: str
    tier: str | None = None


def normalize_payee(value: str) -> str:
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def payee_allowed(payee: str, allowlist: list[str]) -> bool:
    candidate = normalize_payee(payee)
    if not candidate:
        return False
    for entry in allowlist:
        allowed = normalize_payee(entry)
        if not allowed:
            continue
        if candidate == allowed or candidate.startswith(allowed) or allowed.startswith(candidate):
            return True
    return False


class PolicyEngine:
    def __init__(self, db: Session):
        self.db = db

    def evaluate(
        self,
        user_id: int,
        tool_name: str,
        args: dict | None,
        *,
        actor: str = "agent",
        approved: bool = False,
        idempotency_key: str | None = None,
    ) -> PolicyDecision:
        decision = self._decide(user_id, tool_name, args or {}, approved=approved)
        write_audit(
            self.db,
            actor=actor,
            tool=tool_name,
            args=args or {},
            outcome=decision.outcome,
            result=f"{decision.rule_id}: {decision.reason}",
            idempotency_key=idempotency_key,
            user_id=user_id,
            rule_id=decision.rule_id,
        )
        return decision

    def _decide(self, user_id: int, tool_name: str, args: dict, *, approved: bool) -> PolicyDecision:
        if tool_name not in KNOWN_TOOLS:
            return PolicyDecision("DENY", "That tool is not available to the agent.", "UNKNOWN_TOOL")

        if tool_name in READ_TOOLS or tool_name == "categorize":
            return PolicyDecision(
                "ALLOW",
                "Read and labeling actions do not move money.",
                "READ_ALLOW",
                tier="T0",
            )

        if tool_name == "create_proposal":
            return PolicyDecision(
                "ALLOW",
                "Drafting a proposal does not move money.",
                "PROPOSAL_DRAFT",
                tier="T1",
            )

        if tool_name == "set_budget":
            perm = self._permission(user_id, "set_budget")
            tier = perm.tier if perm else "T0"
            if perm is None or tier == "T0":
                return PolicyDecision(
                    "DENY",
                    "Budget changes need at least tier T1.",
                    "T0_NO_BUDGET_WRITE",
                    tier=tier,
                )
            return PolicyDecision("ALLOW", "Budget edits are allowed for this tier.", "BUDGET_WRITE", tier=tier)

        if tool_name not in MONEY_TOOLS:
            return PolicyDecision("DENY", "Unhandled tool.", "UNHANDLED_TOOL")

        action = tool_name
        perm = self._permission(user_id, action)
        if perm is None:
            return PolicyDecision("DENY", "No permission is configured for this action.", "NO_PERMISSION")

        amount = _amount(args.get("amount"))
        if isinstance(amount, PolicyDecision):
            amount.tier = perm.tier
            return amount

        if amount > SYSTEM_MAX_AMOUNT:
            return PolicyDecision(
                "DENY",
                "Amount exceeds the system cap.",
                "SYSTEM_CAP",
                tier=perm.tier,
            )
        if perm.per_action_limit is not None and amount > perm.per_action_limit + 1e-9:
            return PolicyDecision(
                "DENY",
                "Amount exceeds the per-action limit.",
                "PER_ACTION_LIMIT",
                tier=perm.tier,
            )
        spent = self._spent_today(user_id)
        if perm.daily_limit is not None and spent + amount > perm.daily_limit + 1e-9:
            return PolicyDecision(
                "DENY",
                "This would exceed the daily limit.",
                "DAILY_LIMIT",
                tier=perm.tier,
            )

        if tool_name == "schedule_bill":
            payee = str(args.get("payee") or "").strip()
            if not payee:
                return PolicyDecision("DENY", "A payee is required.", "MISSING_PAYEE", tier=perm.tier)
            names = [row.payee_name for row in self.db.query(PayeeAllowlist).filter_by(user_id=user_id).all()]
            if not payee_allowed(payee, names):
                return PolicyDecision(
                    "DENY",
                    "Payee is not on the allowlist.",
                    "PAYEE_NOT_ALLOWLISTED",
                    tier=perm.tier,
                )

        if tool_name == "transfer_to_goal" and not args.get("goal_id"):
            return PolicyDecision("DENY", "A savings goal is required.", "MISSING_GOAL", tier=perm.tier)

        tier = perm.tier
        if tier == "T0":
            return PolicyDecision(
                "DENY",
                "This tier is read-only, so the payment was not executed.",
                "T0_READONLY",
                tier=tier,
            )
        if tier == "T1":
            if approved:
                return PolicyDecision(
                    "DENY",
                    "Propose-only tier cannot execute money movement.",
                    "T1_CANNOT_EXECUTE",
                    tier=tier,
                )
            return PolicyDecision(
                "REQUIRE_APPROVAL",
                "Tier T1 can propose this action but cannot execute it.",
                "T1_PROPOSE_ONLY",
                tier=tier,
            )
        if tier == "T2":
            if approved:
                return PolicyDecision(
                    "ALLOW",
                    "The user approved this action inside the time limit.",
                    "T2_APPROVED",
                    tier=tier,
                )
            return PolicyDecision(
                "REQUIRE_APPROVAL",
                "Tier T2 requires approval before money moves.",
                "T2_REQUIRE_APPROVAL",
                tier=tier,
            )
        if tier == "T3":
            return PolicyDecision("ALLOW", "Within tier T3 limits.", "T3_AUTO", tier=tier)
        return PolicyDecision("DENY", "Unknown permission tier.", "BAD_TIER", tier=tier)

    def _permission(self, user_id: int, action_type: str) -> Permission | None:
        return (
            self.db.query(Permission)
            .filter(Permission.user_id == user_id, Permission.action_type == action_type)
            .one_or_none()
        )

    def _spent_today(self, user_id: int) -> float:
        start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = (
            self.db.query(MoneyMovement)
            .filter(MoneyMovement.user_id == user_id, MoneyMovement.created_at >= start)
            .all()
        )
        return round(sum(row.amount for row in rows), 2)


def _amount(value) -> float | PolicyDecision:
    if value is None or value == "":
        return PolicyDecision("DENY", "Amount is required.", "MISSING_AMOUNT")
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError):
        return PolicyDecision("DENY", "Amount is not a number.", "BAD_AMOUNT")
    if amount <= 0:
        return PolicyDecision("DENY", "Amount must be positive.", "NON_POSITIVE_AMOUNT")
    return amount


def merchant_matches(payee: str, merchant: str) -> bool:
    left = merchant_key(payee)
    right = merchant_key(merchant)
    if not left or not right:
        return False
    return left in right or right in left
