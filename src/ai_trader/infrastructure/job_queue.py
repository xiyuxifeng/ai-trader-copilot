from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ai_trader.domain.jobs import JobLease, JobState
from ai_trader.infrastructure.models import JobModel


class SqlAlchemyJobQueue:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self,
        *,
        kind: str,
        idempotency_key: str,
        payload: dict[str, Any],
        run_after: datetime | None = None,
    ) -> UUID:
        existing = self._session.scalar(
            select(JobModel.id).where(JobModel.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

        job_id = uuid4()
        self._session.add(
            JobModel(
                id=job_id,
                kind=kind,
                state=JobState.QUEUED.value,
                idempotency_key=idempotency_key,
                payload=payload,
                attempts=0,
                run_after=run_after or datetime.now(UTC),
            )
        )
        self._session.flush()
        return job_id

    def lease_next(self, *, lease_seconds: int, now: datetime | None = None) -> JobLease | None:
        lease_started = now or datetime.now(UTC)
        statement = (
            select(JobModel)
            .where(
                JobModel.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
                JobModel.run_after <= lease_started,
                or_(JobModel.locked_until.is_(None), JobModel.locked_until < lease_started),
            )
            .order_by(JobModel.run_after, JobModel.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        model = self._session.scalar(statement)
        if model is None:
            return None

        model.state = JobState.RUNNING.value
        model.attempts += 1
        model.locked_until = lease_started + timedelta(seconds=lease_seconds)
        self._session.flush()
        return JobLease(
            id=model.id,
            kind=model.kind,
            payload=model.payload,
            attempts=model.attempts,
            locked_until=model.locked_until,
        )

    def complete(self, job_id: UUID) -> None:
        model = self._required(job_id)
        model.state = JobState.SUCCEEDED.value
        model.locked_until = None
        model.last_error = None

    def fail(
        self,
        job_id: UUID,
        *,
        error: str,
        retry_at: datetime | None,
    ) -> None:
        model = self._required(job_id)
        model.last_error = error[:4000]
        model.locked_until = None
        if retry_at is None:
            model.state = JobState.FAILED.value
        else:
            model.state = JobState.QUEUED.value
            model.run_after = retry_at

    def _required(self, job_id: UUID) -> JobModel:
        model = self._session.get(JobModel, job_id)
        if model is None:
            raise LookupError(f"job {job_id} does not exist")
        return model

