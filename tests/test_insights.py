"""Insights on the seeded student ledger."""

from app.models import Account, Budget
from insights.service import budget_status, detect_anomalies, goal_views, refresh_recurring, simulate_scenario


def test_budget_covers_fixed_costs_and_income(session):
    status = budget_status(session, 1, "2026-10")
    by_name = {row["category"]: row for row in status["categories"]}
    assert by_name["housing"]["limit"] >= 440
    assert by_name["savings"]["limit"] >= 0
    total = round(sum(row["limit"] for row in status["categories"]), 2)
    assert abs(total - status["income"]) < 0.05
    assert "50/30/20" in status["explanation"]
    assert session.query(Budget).filter_by(month="2026-10").count() >= 5


def test_recurring_price_hike_and_duplicate(session):
    recurring = refresh_recurring(session, 1)
    merchants = " ".join(item["merchant"] for item in recurring)
    assert "NETFLIX" in merchants
    assert "MAPLE COURT" in merchants
    anomalies = detect_anomalies(session, 1, "2026-10")
    types = {item["type"] for item in anomalies}
    assert "duplicate" in types
    assert "price_increase" in types
    assert "unusual" in types


def test_goal_suggestion(session):
    goals = goal_views(session, 1)
    emergency = next(goal for goal in goals if goal["name"] == "Emergency fund")
    assert emergency["current_amount"] == 20
    assert emergency["suggested_weekly"] > 0
    assert emergency["progress"] < 1


def test_what_if_does_not_move_money(session):
    before = session.query(Account).filter_by(type="checking").one().balance
    budgets = session.query(Budget).count()
    result = simulate_scenario(
        session,
        1,
        [
            {"op": "cancel_merchant", "merchant": "NETFLIX.COM"},
            {"op": "cancel_merchant", "merchant": "SPOTIFY USA"},
            {"op": "reduce_category", "category": "dining", "amount": 10},
        ],
    )
    after = session.query(Account).filter_by(type="checking").one().balance
    assert after == before
    assert session.query(Budget).count() == budgets
    assert result["monthly_savings"] > 20
    assert len(result["savings_by_month"]) == 3
    assert result["goal"]["after"] > result["goal"]["before"]
