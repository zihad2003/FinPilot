"""Load the sandbox persona into the local database."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal, init_db
from app.seed_data import reset_and_seed


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = reset_and_seed(db)
        print(f"Seeded {user.name} (user {user.id}) in {db.bind.url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
