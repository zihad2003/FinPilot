"""Budget, recurring bills, anomalies, goals, and what-if math. No money moves here."""

import calendar
from collections import defaultdict
from datetime import date
from statistics import median

from sqlalchemy.orm import Session

from agent.categorize import merchant_key
from app.clock import utcnow
from app.models import Account, Budget, Goal, RecurringItem, Transaction, User

NEEDS = ["housing", "groceries", "transport", "utilities", "education"]
WANTS = ["subscriptions", "dining", "shopping", "other"]
FIXED = ["housing", "utilities"]
ALL_SPEND = NEEDS + WANTS


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def previous_months(month: str, count: int = 3) -> list[str]:
    year, mon = int(month[:4]), int(month[5:7])
    keys = []
    for _ in range(count):
        mon -= 1
        if mon == 0:
            mon = 12
            year -= 1
        keys.append(f"{year:04d}-{mon:02d}")
    return list(reversed(keys))


def _txns(db: Session, user_id: int) -> list[Transaction]:
    account_ids = [row.id for row in db.query(Account.id).filter(Account.user_id == user_id).all()]
    if not account_ids:
        return []
    return db.query(Transaction).filter(Transaction.account_id.in_(account_ids)).all()


def _outflow(txn: Transaction) -> float:
    return round(abs(txn.amount), 2) if txn.amount < 0 else 0.0


def category_totals(txns: list[Transaction], month: str) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for txn in txns:
        if month_key(txn.date) != month or txn.amount >= 0:
            continue
        totals[txn.category or "other"] += _outflow(txn)
    return {key: round(value, 2) for key, value in totals.items()}


def _averages(txns: list[Transaction], month: str) -> dict[str, float]:
    history = previous_months(month, 3)
    sums: dict[str, float] = defaultdict(float)
    for key in history:
        for category, amount in category_totals(txns, key).items():
            sums[category] += amount
    return {category: round(total / 3, 2) for category, total in sums.items()}


def generate_budget(db: Session, user_id: int, month: str) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User was not found")
    income = round(float(user.income_monthly), 2)
    txns = _txns(db, user_id)
    averages = _averages(txns, month)
    limits: dict[str, float] = {}
    for category in FIXED:
        limits[category] = round(averages.get(category, 0), 2)
    fixed_total = round(sum(limits.values()), 2)
    needs_pool = round(max(income * 0.50, fixed_total), 2)
    leftover_needs = round(max(0, needs_pool - fixed_total), 2)
    flexible = ["groceries", "transport", "education"]
    weights = {category: averages.get(category, 0) for category in flexible}
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        for category in flexible:
            limits[category] = 0.0
    else:
        for category, weight in weights.items():
            limits[category] = round(leftover_needs * (weight / weight_sum), 2)

    wants_pool = round(income * 0.30, 2)
    if fixed_total > income * 0.50:
        wants_pool = round(max(0, income * 0.80 - fixed_total), 2)
    want_weights = {category: averages.get(category, 0) * 1.1 for category in WANTS}
    want_sum = sum(want_weights.values())
    if want_sum <= 0:
        for category in WANTS:
            limits[category] = 0.0
    elif want_sum > wants_pool:
        for category, weight in want_weights.items():
            limits[category] = round(wants_pool * (weight / want_sum), 2)
    else:
        for category, weight in want_weights.items():
            limits[category] = round(weight, 2)

    planned = round(sum(limits.values()), 2)
    if planned > income:
        flexible_keys = [key for key in limits if key not in FIXED]
        flex_total = sum(limits[key] for key in flexible_keys)
        room = max(0, income - fixed_total)
        if flex_total > 0:
            scale = room / flex_total
            for key in flexible_keys:
                limits[key] = round(limits[key] * scale, 2)
        planned = round(sum(limits.values()), 2)
    limits["savings"] = round(max(0, income - planned), 2)
    residue = round(income - sum(limits.values()), 2)
    limits["savings"] = round(limits["savings"] + residue, 2)

    db.query(Budget).filter(Budget.user_id == user_id, Budget.month == month).delete()
    for category, limit_amount in limits.items():
        db.add(Budget(user_id=user_id, month=month, category=category, limit_amount=limit_amount))
    db.commit()
    return budget_status(db, user_id, month)


def budget_status(db: Session, user_id: int, month: str) -> dict:
    rows = db.query(Budget).filter(Budget.user_id == user_id, Budget.month == month).all()
    if not rows:
        return generate_budget(db, user_id, month)
    user = db.get(User, user_id)
    income = round(float(user.income_monthly), 2) if user else 0
    actuals = category_totals(_txns(db, user_id), month)
    categories = []
    for row in sorted(rows, key=lambda item: item.category):
        spent = round(actuals.get(row.category, 0), 2)
        categories.append(
            {
                "category": row.category,
                "limit": round(row.limit_amount, 2),
                "actual": spent,
                "remaining": round(row.limit_amount - spent, 2),
            }
        )
    return {
        "month": month,
        "income": income,
        "baseline": {
            "needs": round(income * 0.50, 2),
            "wants": round(income * 0.30, 2),
            "savings": round(income * 0.20, 2),
        },
        "categories": categories,
        "explanation": (
            f"Baseline 50/30/20 on monthly income {income:.0f} is "
            f"needs {income * 0.50:.0f}, wants {income * 0.30:.0f}, savings {income * 0.20:.0f}. "
            "Rent and phone stay at their 3-month average. Other categories follow that history, "
            "and whatever is left is the savings limit."
        ),
    }


def detect_recurring(txns: list[Transaction]) -> list[dict]:
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for txn in txns:
        if txn.amount < 0:
            groups[merchant_key(txn.merchant)].append(txn)
    found = []
    for key, items in groups.items():
        if len(items) < 3 or not key:
            continue
        items.sort(key=lambda txn: txn.date)
        intervals = [(items[index].date - items[index - 1].date).days for index in range(1, len(items))]
        typical = median(intervals) if intervals else 0
        if 25 <= typical <= 35:
            frequency = "monthly"
        elif 6 <= typical <= 8:
            frequency = "weekly"
        else:
            continue
        amounts = [abs(txn.amount) for txn in items]
        if min(amounts) <= 0 or max(amounts) / min(amounts) > 1.35:
            continue
        last = items[-1]
        next_due = date.fromordinal(last.date.toordinal() + int(round(typical)))
        found.append(
            {
                "merchant": last.merchant,
                "merchant_key": key,
                "amount": round(median(amounts), 2),
                "frequency": frequency,
                "next_due": next_due.isoformat(),
                "status": "active",
                "transaction_ids": [txn.id for txn in items],
            }
        )
    found.sort(key=lambda item: item["merchant"])
    return found


def refresh_recurring(db: Session, user_id: int) -> list[dict]:
    found = detect_recurring(_txns(db, user_id))
    db.query(RecurringItem).filter(RecurringItem.user_id == user_id).delete()
    for item in found:
        db.add(
            RecurringItem(
                user_id=user_id,
                merchant=item["merchant"],
                amount=item["amount"],
                frequency=item["frequency"],
                next_due=date.fromisoformat(item["next_due"]),
                status="active",
            )
        )
    db.commit()
    return found


def detect_anomalies(db: Session, user_id: int, month: str | None = None) -> list[dict]:
    txns = _txns(db, user_id)
    flags: list[dict] = []
    grouped: dict[tuple[str, float], list[Transaction]] = defaultdict(list)
    for txn in txns:
        if txn.amount < 0:
            grouped[(merchant_key(txn.merchant), round(abs(txn.amount), 2))].append(txn)
    for (key, amount), items in grouped.items():
        items.sort(key=lambda txn: (txn.date, txn.id))
        for earlier, later in zip(items, items[1:]):
            gap = (later.date - earlier.date).days
            if gap <= 3:
                flags.append(
                    {
                        "type": "duplicate",
                        "merchant": later.merchant,
                        "amount": amount,
                        "transaction_ids": [earlier.id, later.id],
                        "detail": f"Two charges of {amount:.2f} at {key} are {gap} day(s) apart.",
                    }
                )

    recurring_keys = {item["merchant_key"] for item in detect_recurring(txns)}
    by_merchant: dict[str, list[Transaction]] = defaultdict(list)
    for txn in txns:
        if txn.amount < 0:
            by_merchant[merchant_key(txn.merchant)].append(txn)
    for key, items in by_merchant.items():
        if key not in recurring_keys or len(items) < 4:
            continue
        items.sort(key=lambda txn: (txn.date, txn.id))
        amounts = [abs(txn.amount) for txn in items]
        latest = amounts[-1]
        prior = sorted(amounts[:-1])
        midpoint = prior[len(prior) // 2]
        if midpoint > 0 and latest > midpoint * 1.1:
            flags.append(
                {
                    "type": "price_increase",
                    "merchant": items[-1].merchant,
                    "amount": round(latest, 2),
                    "transaction_ids": [txn.id for txn in items[-2:]],
                    "detail": (
                        f"{key} is now {latest:.2f}, above the earlier typical amount of {midpoint:.2f}."
                    ),
                }
            )
    for txn in txns:
        if txn.amount >= 0:
            continue
        if (txn.category or "") in {"housing", "education", "income"}:
            continue
        if abs(txn.amount) < 150:
            continue
        key = merchant_key(txn.merchant)
        if sum(1 for other in txns if merchant_key(other.merchant) == key) == 1:
            flags.append(
                {
                    "type": "unusual",
                    "merchant": txn.merchant,
                    "amount": round(abs(txn.amount), 2),
                    "transaction_ids": [txn.id],
                    "detail": f"One-off charge of {abs(txn.amount):.2f} at {txn.merchant}.",
                }
            )

    target = month or month_key(utcnow().date())
    rows = db.query(Budget).filter(Budget.user_id == user_id, Budget.month == target).all()
    if rows:
        actuals = category_totals(txns, target)
        year, mon = int(target[:4]), int(target[5:7])
        today = utcnow().date()
        day = today.day if month_key(today) == target else 28
        for row in rows:
            spent = actuals.get(row.category, 0)
            if row.limit_amount <= 0 or row.category in {"housing", "utilities", "subscriptions", "savings"}:
                continue
            if spent > row.limit_amount:
                flags.append(
                    {
                        "type": "budget_exceeded",
                        "merchant": row.category,
                        "amount": round(spent, 2),
                        "transaction_ids": [],
                        "detail": (
                            f"{row.category} spending {spent:.2f} is over the {row.limit_amount:.2f} limit."
                        ),
                    }
                )
            elif day >= 7 and spent > row.limit_amount * 0.85:
                dim = calendar.monthrange(year, mon)[1]
                projected = spent / day * dim
                if projected > row.limit_amount:
                    flags.append(
                        {
                            "type": "budget_projected",
                            "merchant": row.category,
                            "amount": round(projected, 2),
                            "transaction_ids": [],
                            "detail": (
                                f"{row.category} is on pace for {projected:.2f}, over the {row.limit_amount:.2f} limit."
                            ),
                        }
                    )
    return flags


def goal_views(db: Session, user_id: int) -> list[dict]:
    today = utcnow().date()
    views = []
    for goal in db.query(Goal).filter(Goal.user_id == user_id).order_by(Goal.id).all():
        remaining = max(0, goal.target_amount - goal.current_amount)
        days = max(0, (goal.target_date - today).days)
        weeks = max(1, days / 7)
        views.append(
            {
                "id": goal.id,
                "name": goal.name,
                "target_amount": round(goal.target_amount, 2),
                "target_date": goal.target_date.isoformat(),
                "current_amount": round(goal.current_amount, 2),
                "progress": round(goal.current_amount / goal.target_amount, 4) if goal.target_amount else 0,
                "suggested_weekly": round(remaining / weeks, 2),
                "remaining": round(remaining, 2),
            }
        )
    return views


def simulate_scenario(db: Session, user_id: int, changes: list[dict]) -> dict:
    """Recompute the next three months. Does not write budgets, balances, or goals."""
    txns = _txns(db, user_id)
    month = month_key(utcnow().date())
    before = _averages(txns, month)
    for category in ALL_SPEND:
        before.setdefault(category, 0.0)
    after = dict(before)
    notes = []
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for txn in txns:
        if txn.amount < 0:
            groups[merchant_key(txn.merchant)].append(txn)

    for change in changes or []:
        op = change.get("op")
        if op == "cancel_merchant":
            key = merchant_key(str(change.get("merchant") or ""))
            items = groups.get(key) or []
            if not items:
                notes.append(f"No history for {change.get('merchant')}.")
                continue
            monthly = round(sum(abs(txn.amount) for txn in items) / max(1, len({month_key(txn.date) for txn in items})), 2)
            category = items[-1].category or "other"
            after[category] = round(max(0, after.get(category, 0) - monthly), 2)
            notes.append(f"Canceling {items[-1].merchant} removes about {monthly:.2f} a month from {category}.")
        elif op == "reduce_category":
            category = str(change.get("category") or "other")
            amount = round(float(change.get("amount") or 0), 2)
            after[category] = round(max(0, after.get(category, 0) - amount), 2)
            notes.append(f"Reducing {category} by {amount:.2f} a month.")

    before_total = round(sum(before.get(category, 0) for category in ALL_SPEND), 2)
    after_total = round(sum(after.get(category, 0) for category in ALL_SPEND), 2)
    monthly_savings = round(max(0, before_total - after_total), 2)
    goals = goal_views(db, user_id)
    primary = goals[0] if goals else None
    goal_after = None
    if primary:
        goal_after = round(primary["current_amount"] + monthly_savings * 3, 2)
    return {
        "months": 3,
        "before_by_category": {category: round(before.get(category, 0), 2) for category in ALL_SPEND},
        "after_by_category": {category: round(after.get(category, 0), 2) for category in ALL_SPEND},
        "monthly_savings": monthly_savings,
        "projected_savings": round(monthly_savings * 3, 2),
        "savings_by_month": [round(monthly_savings * step, 2) for step in (1, 2, 3)],
        "goal": None
        if primary is None
        else {
            "name": primary["name"],
            "before": primary["current_amount"],
            "after": goal_after,
            "target": primary["target_amount"],
        },
        "narrative": " ".join(notes) or "No changes were applied.",
        "explanation": "Figures use the average of the previous three months. No money is moved.",
    }
