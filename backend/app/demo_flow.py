"""Demo flow used by scripts/demo_run.py and the test suite."""

from fastapi.testclient import TestClient


def run_demo_flow(client: TestClient) -> dict:
    steps: list[dict] = []

    def record(name: str, ok: bool, detail: str, extra: dict | None = None):
        steps.append({"name": name, "ok": ok, "detail": detail, **(extra or {})})

    health = client.get("/health")
    record("health", health.status_code == 200, f"status {health.status_code}")

    accounts = client.get("/accounts")
    balance = accounts.json()[0]["balance"] if accounts.status_code == 200 else None
    record("accounts", accounts.status_code == 200 and balance is not None, f"balance {balance}")

    budget = client.get("/insights/budget", params={"month": "2026-10"})
    categories = {row["category"] for row in budget.json().get("categories", [])} if budget.status_code == 200 else set()
    record("budget", "housing" in categories, f"categories {sorted(categories)}")

    denied = client.post(
        "/transfers",
        json={"goal_id": 1, "amount": 500},
        headers={"Idempotency-Key": "demo-over-limit"},
    )
    record(
        "over_limit_denied",
        denied.status_code == 403 and denied.json().get("code") == "PER_ACTION_LIMIT",
        f"status {denied.status_code} code {denied.json().get('code') if denied.headers.get('content-type','').startswith('application/json') else ''}",
    )

    proposals = client.get("/proposals", params={"status": "pending"})
    pending = proposals.json() if proposals.status_code == 200 else []
    phone = next((item for item in pending if item["payload"].get("payee") == "T-MOBILE"), None)
    if phone is None:
        record("approve_bill", False, "no pending phone bill")
    else:
        before = client.get("/accounts").json()[0]["balance"]
        approved = client.post(
            f"/proposals/{phone['id']}/approve",
            headers={"Idempotency-Key": f"demo-approve-{phone['id']}"},
        )
        after = client.get("/accounts").json()[0]["balance"]
        record(
            "approve_bill",
            approved.status_code == 200 and approved.json().get("executed") is True and after == round(before - 35, 2),
            f"status {approved.status_code} balance {before} -> {after}",
        )
        again = client.post(
            f"/proposals/{phone['id']}/approve",
            headers={"Idempotency-Key": f"demo-approve-{phone['id']}"},
        )
        record("duplicate_approve", again.status_code == 409, f"status {again.status_code}")

    chat = client.post("/chat", json={"message": "How much did I spend on food last month?"})
    chat_body = chat.json()
    record(
        "chat_without_model",
        chat.status_code == 200 and bool(chat_body.get("error")),
        chat_body.get("error") or f"status {chat.status_code}",
    )
    still = client.get("/accounts")
    audit = client.get("/audit")
    record(
        "dashboard_after_chat_error",
        still.status_code == 200 and audit.status_code == 200,
        f"accounts {still.status_code} audit {audit.status_code}",
    )
    denied_rows = [row for row in audit.json() if row.get("rule_id") == "PER_ACTION_LIMIT"]
    record("audit_has_denial", len(denied_rows) >= 1, f"denials {len(denied_rows)}")

    return {"ok": all(step["ok"] for step in steps), "steps": steps, "audit_count": len(audit.json())}
