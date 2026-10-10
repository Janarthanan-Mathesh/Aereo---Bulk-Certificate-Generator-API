from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.main import app
from app.models import Base


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)

    from app.services import jobs

    artifacts_dir = Path(__file__).parent / ".test_artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(jobs, "STORAGE_DIR", artifacts_dir / "generated")
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    shutil.rmtree(artifacts_dir, ignore_errors=True)


@pytest.fixture
def valid_payload():
    return {
        "event_name": "Geospatial AI Workshop",
        "issuer": "Aereo Learning Team",
        "issue_date": "2026-10-10",
        "recipients": [
            {"name": "Arun Kumar", "certificate_id": "AERO-2026-001"},
            {"name": "Priya S", "certificate_id": "AERO-2026-002"},
        ],
    }
