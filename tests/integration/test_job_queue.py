from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_trader.domain.jobs import JobState
from ai_trader.infrastructure.job_queue import SqlAlchemyJobQueue
from ai_trader.infrastructure.models import Base, JobModel


def test_enqueue_is_idempotent_and_lease_is_recoverable() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        queue = SqlAlchemyJobQueue(session)
        first_id = queue.enqueue(
            kind="system.health",
            idempotency_key="health:2026-10-23",
            payload={"source": "test"},
            run_after=now,
        )
        repeated_id = queue.enqueue(
            kind="system.health",
            idempotency_key="health:2026-10-23",
            payload={"source": "ignored"},
            run_after=now,
        )
        assert first_id == repeated_id

        lease = queue.lease_next(lease_seconds=30, now=now)
        assert lease is not None
        assert lease.id == first_id
        assert lease.attempts == 1
        assert queue.lease_next(lease_seconds=30, now=now) is None

        recovered = queue.lease_next(lease_seconds=30, now=now + timedelta(seconds=31))
        assert recovered is not None
        assert recovered.id == first_id
        assert recovered.attempts == 2

        queue.complete(first_id)
        session.commit()
        assert session.get(JobModel, first_id).state == JobState.SUCCEEDED.value

