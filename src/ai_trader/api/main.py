from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from ai_trader.api.schemas import (
    ComponentHealth,
    HealthResponse,
    OnboardingRequest,
    OnboardingResponse,
    ProfileResponse,
    TodayResponse,
)
from ai_trader.application.onboarding import CompleteOnboarding, CompleteOnboardingHandler
from ai_trader.application.today import build_today_view
from ai_trader.config import get_settings
from ai_trader.infrastructure.database import SessionFactory, get_session
from ai_trader.infrastructure.models import WorkerHeartbeatModel
from ai_trader.infrastructure.repositories import SqlAlchemyProfileRepository, uow_factory

SessionDep = Annotated[Session, Depends(get_session)]


def create_app(session_factory: sessionmaker[Session] = SessionFactory) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI-Trader Copilot API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    def health(session: SessionDep) -> HealthResponse:
        try:
            session.execute(text("SELECT 1"))
            database = ComponentHealth(status="ok", message="业务数据库连接正常")
        except Exception:
            database = ComponentHealth(status="unavailable", message="业务数据库暂不可用")
            return HealthResponse(
                status="degraded",
                database=database,
                worker=ComponentHealth(status="unavailable", message="无法检查后台任务"),
                market_data=ComponentHealth(status="not_configured", message="行情服务尚未配置"),
                ai_service=ComponentHealth(status="not_configured", message="AI 服务尚未配置"),
            )

        heartbeat = session.scalar(
            select(WorkerHeartbeatModel).order_by(WorkerHeartbeatModel.last_seen_at.desc()).limit(1)
        )
        worker_ok = bool(
            heartbeat
            and _as_utc(heartbeat.last_seen_at)
            >= datetime.now(UTC) - timedelta(seconds=settings.worker_heartbeat_seconds * 3)
        )
        worker = ComponentHealth(
            status="ok" if worker_ok else "unavailable",
            message="后台任务运行正常" if worker_ok else "后台任务尚未启动",
        )
        return HealthResponse(
            status="ok" if worker_ok else "degraded",
            database=database,
            worker=worker,
            market_data=ComponentHealth(status="not_configured", message="行情服务尚未配置"),
            ai_service=ComponentHealth(status="not_configured", message="AI 服务尚未配置"),
        )

    @app.get("/api/v1/profile", response_model=ProfileResponse | None)
    def get_profile(session: SessionDep) -> ProfileResponse | None:
        repository = SqlAlchemyProfileRepository(session)
        profile = repository.get()
        policy = repository.current_policy()
        if profile is None or policy is None:
            return None
        return _profile_response(profile, policy.version)

    @app.post("/api/v1/onboarding", response_model=OnboardingResponse)
    def complete_onboarding(payload: OnboardingRequest) -> OnboardingResponse:
        handler = CompleteOnboardingHandler(uow_factory(session_factory))
        try:
            result = handler(
                CompleteOnboarding(
                    market=payload.market,
                    holding_horizon=payload.holding_horizon,
                    risk_level=payload.risk_level,
                    single_position_limit=payload.single_position_limit,
                    notification_time=payload.notification_time,
                )
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return OnboardingResponse(
            profile=_profile_response(result.profile, result.policy.version),
            changed=result.changed,
        )

    @app.get("/api/v1/today", response_model=TodayResponse)
    def today(session: SessionDep) -> TodayResponse:
        view = build_today_view(SqlAlchemyProfileRepository(session).get())
        return TodayResponse(**asdict(view))

    return app


def _profile_response(profile, policy_version: int) -> ProfileResponse:
    return ProfileResponse(
        id=profile.id,
        market=profile.market,
        holding_horizon=profile.holding_horizon,
        risk_level=profile.risk_level,
        single_position_limit=profile.single_position_limit,
        notification_time=profile.notification_time,
        risk_policy_version=policy_version,
        live_trading_enabled=False,
        updated_at=profile.updated_at,
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


app = create_app()
