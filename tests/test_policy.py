"""Policy engine cases TC-01 through TC-06 and TC-10, plus the surrounding rules."""

from datetime import timedelta

from app.clock import clock
from app.models import Account, AuditLog, MoneyMovement, Permission
from app.services.bank import approve_proposal, request_money_movement
from policy.engine import PolicyEngine


def _perm(session, action):
    return session.query(Permission).filter_by(action_type=action).one()


def _balance(session):
    return session.query(Account).filter_by(type="checking").one().balance


def test_tc01_transfer_over_per_action_limit(session):
    before = _balance(session)
    decision = PolicyEngine(session).evaluate(1, "transfer_to_goal", {"goal_id": 1, "amount": 80})
    assert decision.outcome == "DENY"
    assert decision.rule_id == "PER_ACTION_LIMIT"
    assert session.query(AuditLog).filter_by(rule_id="PER_ACTION_LIMIT").count() == 1
    assert _balance(session) == before


def test_schedule_over_limit_denied(session):
    decision = PolicyEngine(session).evaluate(1, "schedule_bill", {"payee": "NETFLIX.COM", "amount": 900})
    assert decision.outcome == "DENY"
    assert decision.rule_id == "PER_ACTION_LIMIT"


def test_tc02_t2_within_limit_waits_for_approval(session):
    before = _balance(session)
    outcome = request_money_movement(
        session,
        user_id=1,
        tool_name="schedule_bill",
        args={"payee": "NETFLIX.COM", "amount": 18.99},
        idempotency_key="tc02",
        actor="agent",
    )
    assert outcome["outcome"] == "REQUIRE_APPROVAL"
    assert outcome["executed"] is False
    assert outcome["proposal"].status == "pending"
    assert _balance(session) == before
    approved = approve_proposal(session, 1, outcome["proposal"].id, "tc02-approve")
    assert approved["executed"] is True
    assert round(before - _balance(session), 2) == 18.99


def test_tc03_expired_approval_executes_nothing(session, monkeypatch):
    outcome = request_money_movement(
        session,
        user_id=1,
        tool_name="schedule_bill",
        args={"payee": "SPOTIFY", "amount": 11.99},
        idempotency_key="tc03",
        actor="agent",
    )
    before = _balance(session)
    original = clock.now

    def later():
        return original() + timedelta(minutes=16)

    monkeypatch.setattr(clock, "now", later)
    try:
        approve_proposal(session, 1, outcome["proposal"].id, "tc03-approve")
        assert False, "expired approval should fail"
    except Exception as exc:
        assert getattr(exc, "code", "") == "proposal_expired"
    assert _balance(session) == before
    assert session.query(AuditLog).filter_by(rule_id="APPROVAL_EXPIRED").count() == 1


def test_tc04_same_execution_twice(session):
    goal_id = 1
    before = _balance(session)
    first = request_money_movement(
        session,
        user_id=1,
        tool_name="transfer_to_goal",
        args={"goal_id": goal_id, "amount": 3},
        idempotency_key="tc04",
        actor="agent",
    )
    assert first["executed"] is True
    try:
        request_money_movement(
            session,
            user_id=1,
            tool_name="transfer_to_goal",
            args={"goal_id": goal_id, "amount": 3},
            idempotency_key="tc04",
            actor="agent",
        )
        assert False, "duplicate key should fail"
    except Exception as exc:
        assert getattr(exc, "code", "") == "duplicate_idempotency_key"
    assert round(before - _balance(session), 2) == 3


def test_tc06_payee_not_allowlisted(session):
    before = _balance(session)
    decision = PolicyEngine(session).evaluate(1, "schedule_bill", {"payee": "EVIL CORP", "amount": 10})
    assert decision.outcome == "DENY"
    assert decision.rule_id == "PAYEE_NOT_ALLOWLISTED"
    assert _balance(session) == before


def test_tc10_t0_denies_and_files_blocked_proposal(session):
    perm = _perm(session, "schedule_bill")
    perm.tier = "T0"
    session.commit()
    before = _balance(session)
    outcome = request_money_movement(
        session,
        user_id=1,
        tool_name="schedule_bill",
        args={"payee": "NETFLIX.COM", "amount": 18.99},
        idempotency_key="tc10",
        actor="agent",
    )
    assert outcome["outcome"] == "DENY"
    assert outcome["rule_id"] == "T0_READONLY"
    assert outcome["proposal"].status == "blocked"
    assert _balance(session) == before


def test_daily_limit(session):
    session.add(
        MoneyMovement(
            user_id=1,
            action_type="transfer_to_goal",
            amount=18,
            payee=None,
            idempotency_key="already-spent",
            created_at=clock.now(),
        )
    )
    session.commit()
    decision = PolicyEngine(session).evaluate(1, "transfer_to_goal", {"goal_id": 1, "amount": 5})
    assert decision.rule_id == "DAILY_LIMIT"


def test_t3_within_limits_allows(session):
    decision = PolicyEngine(session).evaluate(1, "transfer_to_goal", {"goal_id": 1, "amount": 5})
    assert decision.outcome == "ALLOW"
    assert decision.rule_id == "T3_AUTO"


def test_t1_propose_only_never_executes(session):
    perm = _perm(session, "transfer_to_goal")
    perm.tier = "T1"
    session.commit()
    outcome = request_money_movement(
        session,
        user_id=1,
        tool_name="transfer_to_goal",
        args={"goal_id": 1, "amount": 4},
        idempotency_key="t1",
        actor="agent",
    )
    assert outcome["proposal"].status == "proposed"
    before = _balance(session)
    try:
        approve_proposal(session, 1, outcome["proposal"].id, "t1-approve")
        assert False
    except Exception as exc:
        assert getattr(exc, "status_code", 0) in {403, 409}
    assert _balance(session) == before


def test_read_and_budget_tiers(session):
    read = PolicyEngine(session).evaluate(1, "get_transactions", {"category": "groceries"})
    assert read.outcome == "ALLOW"
    denied = PolicyEngine(session).evaluate(1, "set_budget", {"category": "dining", "limit": 40})
    _perm(session, "set_budget").tier = "T0"
    session.commit()
    denied = PolicyEngine(session).evaluate(1, "set_budget", {"category": "dining", "limit": 40})
    assert denied.rule_id == "T0_NO_BUDGET_WRITE"
    _perm(session, "set_budget").tier = "T1"
    session.commit()
    allowed = PolicyEngine(session).evaluate(1, "set_budget", {"category": "dining", "limit": 40})
    assert allowed.outcome == "ALLOW"


def test_unknown_tool_system_cap_and_bad_amount(session):
    engine = PolicyEngine(session)
    assert engine.evaluate(1, "update_limits", {"per_action_limit": 99999}).rule_id == "UNKNOWN_TOOL"
    assert engine.evaluate(1, "schedule_bill", {"payee": "NETFLIX.COM", "amount": 50000}).rule_id == "SYSTEM_CAP"
    assert engine.evaluate(1, "schedule_bill", {"payee": "NETFLIX.COM", "amount": -5}).rule_id == "NON_POSITIVE_AMOUNT"
    assert engine.evaluate(1, "schedule_bill", {"payee": "NETFLIX.COM"}).rule_id == "MISSING_AMOUNT"
    assert engine.evaluate(1, "schedule_bill", {"amount": 10}).rule_id == "MISSING_PAYEE"
    assert engine.evaluate(1, "transfer_to_goal", {"amount": 1}).rule_id == "MISSING_GOAL"


def test_t2_approved_flag_allows(session):
    decision = PolicyEngine(session).evaluate(
        1, "schedule_bill", {"payee": "NETFLIX.COM", "amount": 10}, approved=True
    )
    assert decision.outcome == "ALLOW"
    assert decision.rule_id == "T2_APPROVED"


def test_t1_approved_flag_still_denies(session):
    _perm(session, "schedule_bill").tier = "T1"
    session.commit()
    decision = PolicyEngine(session).evaluate(
        1, "schedule_bill", {"payee": "NETFLIX.COM", "amount": 10}, approved=True
    )
    assert decision.rule_id == "T1_CANNOT_EXECUTE"


def test_remaining_policy_branches(session):
    from policy.engine import merchant_matches, payee_allowed

    assert payee_allowed("", ["NETFLIX"]) is False
    assert payee_allowed("NETFLIX", ["***", "NETFLIX.COM"]) is True
    assert PolicyEngine(session).evaluate(1, "create_proposal", {"action": "schedule_bill"}).outcome == "ALLOW"
    session.query(Permission).filter_by(action_type="schedule_bill").delete()
    session.commit()
    assert PolicyEngine(session).evaluate(1, "schedule_bill", {"payee": "NETFLIX.COM", "amount": 10}).rule_id == "NO_PERMISSION"
    session.add(Permission(user_id=1, action_type="schedule_bill", tier="T9", per_action_limit=500, daily_limit=1500))
    session.commit()
    assert PolicyEngine(session).evaluate(1, "schedule_bill", {"payee": "NETFLIX.COM", "amount": "nope"}).rule_id == "BAD_AMOUNT"
    assert PolicyEngine(session).evaluate(1, "schedule_bill", {"payee": "NETFLIX.COM", "amount": 10}).rule_id == "BAD_TIER"
    assert merchant_matches("", "NETFLIX") is False
    assert merchant_matches("NETFLIX", "NETFLIX.COM") is True
