"""Sandbox bank endpoints."""

from app.models import Account, Transaction
from app.seed_data import DEMO_ACCOUNT_NUMBER


def test_accounts_and_masking(client):
    accounts = client.get("/accounts")
    assert accounts.status_code == 200
    body = accounts.json()
    assert body[0]["balance"] > 0
    assert DEMO_ACCOUNT_NUMBER not in accounts.text
    assert body[0]["account_number_masked"].endswith("4567")


def test_transactions_filters_and_masking(client):
    response = client.get("/transactions", params={"category": "housing", "limit": 20})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(row["category"] == "housing" for row in rows)
    assert DEMO_ACCOUNT_NUMBER not in response.text


def test_csv_import_and_reject_bad_file(client, session):
    before = session.query(Account).filter_by(type="checking").one().balance
    csv_text = "date,description,amount,currency\n2026-10-10,CAMPUS BOOKS,-12.50,USD\n"
    ok = client.post(
        "/transactions/import",
        files={"file": ("spend.csv", csv_text, "text/csv")},
    )
    assert ok.status_code == 200
    assert ok.json()["imported"] == 1
    after = session.query(Account).filter_by(type="checking").one().balance
    assert round(after - before, 2) == -12.50
    bad = client.post("/transactions/import", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert bad.status_code == 400


def test_schedule_bill_requires_approval_and_idempotency(client, session):
    before = session.query(Account).filter_by(type="checking").one().balance
    missing = client.post("/bills/schedule", json={"payee": "NETFLIX.COM", "amount": 18.99})
    assert missing.status_code == 422
    held = client.post(
        "/bills/schedule",
        json={"payee": "NETFLIX.COM", "amount": 18.99, "date": "2026-10-20"},
        headers={"Idempotency-Key": "bill-1"},
    )
    assert held.status_code == 200
    assert held.json()["executed"] is False
    assert held.json()["outcome"] == "REQUIRE_APPROVAL"
    assert held.json()["proposal"]["status"] == "pending"
    assert session.query(Account).filter_by(type="checking").one().balance == before
    duplicate = client.post(
        "/bills/schedule",
        json={"payee": "NETFLIX.COM", "amount": 18.99},
        headers={"Idempotency-Key": "bill-1"},
    )
    assert duplicate.status_code == 409


def test_transfer_executes_within_t3_limit_once(client, session):
    goal_id = client.get("/goals").json()[0]["id"]
    before = session.query(Account).filter_by(type="checking").one().balance
    goal_before = client.get("/goals").json()[0]["current_amount"]
    first = client.post(
        "/transfers",
        json={"goal_id": goal_id, "amount": 4},
        headers={"Idempotency-Key": "roundup-1"},
    )
    assert first.status_code == 200
    assert first.json()["executed"] is True
    second = client.post(
        "/transfers",
        json={"goal_id": goal_id, "amount": 4},
        headers={"Idempotency-Key": "roundup-1"},
    )
    assert second.status_code == 409
    account = session.query(Account).filter_by(type="checking").one()
    assert round(before - account.balance, 2) == 4
    assert round(client.get("/goals").json()[0]["current_amount"] - goal_before, 2) == 4


def test_create_goal_and_permissions_patch(client):
    created = client.post(
        "/goals",
        json={"name": "Laptop", "target_amount": 400, "target_date": "2026-12-01"},
    )
    assert created.status_code == 200
    assert any(goal["name"] == "Laptop" for goal in created.json())
    updated = client.patch(
        "/permissions/transfer_to_goal",
        json={"tier": "T2", "per_action_limit": 25, "daily_limit": 40},
    )
    assert updated.status_code == 200
    assert updated.json()["tier"] == "T2"


def test_category_correction_is_reused(client):
    uber = client.get("/transactions", params={"merchant": "UBER"}).json()[0]
    corrected = client.patch(f"/transactions/{uber['id']}/category", json={"category": "dining"})
    assert corrected.status_code == 200
    assert corrected.json()["source"] == "user"
    again = client.get("/transactions", params={"merchant": "UBER"}).json()
    assert all(row["category"] == "dining" for row in again)


def test_audit_export(client):
    exported = client.get("/audit/export")
    assert exported.status_code == 200
    assert "policy_outcome" in exported.text
    assert "text/csv" in exported.headers["content-type"]


def test_docs_available(client):
    response = client.get("/openapi.json")
    paths = response.json()["paths"]
    for path in ("/accounts", "/transactions", "/bills/schedule", "/transfers", "/goals", "/chat", "/audit"):
        assert path in paths


def test_seed_has_history(session):
    assert session.query(Transaction).count() > 40
