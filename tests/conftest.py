"""Shared fixtures. Tests never call a live model."""

import os
import tempfile
from pathlib import Path

_db = Path(tempfile.mkdtemp(prefix="finpilot-tests-")) / "unused.db"
os.environ["DATABASE_URL"] = "sqlite:///" + _db.as_posix()
os.environ["SEED_ON_START"] = "0"
os.environ["FINPILOT_DISABLE_LLM"] = "1"
os.environ["LLM_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base
from app.rate_limit import reset_rate_limit
from app.seed_data import seed_demo

_security_results: list[tuple[str, str]] = []


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    seed_demo(db)
    yield db
    db.close()
    engine.dispose()


@pytest.fixture
def client(session):
    def override():
        yield session

    app.dependency_overrides[get_db] = override
    reset_rate_limit()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _quiet_rate():
    from app.config import settings

    settings.chat_rate_limit = 30
    reset_rate_limit()
    yield
    reset_rate_limit()


def pytest_runtest_logreport(report):
    if report.when == "call" and "security" in report.nodeid:
        _security_results.append((report.nodeid.split("::")[-1], report.outcome))


def pytest_sessionfinish(session, exitstatus):
    if not _security_results:
        return
    print("\nSecurity test summary")
    print(f"{'Test':<62} Result")
    for name, outcome in _security_results:
        print(f"{name:<62} {outcome.upper()}")
