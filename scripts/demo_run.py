"""Run the sandbox demo and write an operation log under docs/evidence/."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("FINPILOT_DISABLE_LLM", "1")
os.environ.setdefault("SEED_ON_START", "0")
os.environ.setdefault("LLM_API_KEY", "")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="finpilot-demo-"))
    os.environ["DATABASE_URL"] = "sqlite:///" + (tmp / "demo.db").as_posix()

    from fastapi.testclient import TestClient

    from app.db import SessionLocal, init_db
    from app.demo_flow import run_demo_flow
    from app.main import app
    from app.seed_data import reset_and_seed

    init_db()
    db = SessionLocal()
    try:
        reset_and_seed(db)
    finally:
        db.close()

    with TestClient(app) as client:
        report = run_demo_flow(client)

    evidence = ROOT / "docs" / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = evidence / f"demo-{stamp}.json"
    payload = {
        "generated_at": stamp,
        "sandbox": True,
        "ok": report["ok"],
        "steps": report["steps"],
        "audit_count": report["audit_count"],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {path}")
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
