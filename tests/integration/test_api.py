from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ai_trader.api.main import create_app
from ai_trader.infrastructure.database import get_session
from ai_trader.infrastructure.models import Base


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    app = create_app(factory)

    def test_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        yield client


def test_onboarding_and_truthful_today_state(client: TestClient) -> None:
    assert client.get("/api/v1/profile").json() is None
    before = client.get("/api/v1/today").json()
    assert before["setup_required"] is True

    response = client.post(
        "/api/v1/onboarding",
        json={
            "holding_horizon": "swing",
            "risk_level": "balanced",
            "single_position_limit": "0.20",
            "notification_time": "18:30",
        },
    )
    assert response.status_code == 200
    assert response.json()["profile"]["live_trading_enabled"] is False
    assert response.json()["profile"]["risk_policy_version"] == 1

    today = client.get("/api/v1/today").json()
    assert today["setup_required"] is False
    assert today["data_as_of"] is None
    assert "不生成操作建议" in today["market_summary"]


def test_onboarding_is_idempotent_for_unchanged_settings(client: TestClient) -> None:
    payload = {
        "holding_horizon": "short",
        "risk_level": "conservative",
        "single_position_limit": "0.10",
        "notification_time": "18:30",
    }

    assert client.post("/api/v1/onboarding", json=payload).json()["changed"] is True
    repeated = client.post("/api/v1/onboarding", json=payload).json()

    assert repeated["changed"] is False
    assert repeated["profile"]["risk_policy_version"] == 1
