from contextlib import AbstractContextManager
from datetime import UTC
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, sessionmaker

from ai_trader.domain.profile import (
    HoldingHorizon,
    Market,
    RiskLevel,
    RiskPolicy,
    UserProfile,
)
from ai_trader.infrastructure.models import RiskPolicyVersionModel, UserProfileModel


class SqlAlchemyProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> UserProfile | None:
        model = self._session.scalars(select(UserProfileModel).limit(1)).first()
        return _profile_from_model(model) if model else None

    def current_policy(self) -> RiskPolicy | None:
        statement: Select[tuple[RiskPolicyVersionModel]] = select(
            RiskPolicyVersionModel
        ).order_by(RiskPolicyVersionModel.version.desc())
        model = self._session.scalars(statement.limit(1)).first()
        return _policy_from_model(model) if model else None

    def save(self, profile: UserProfile, policy: RiskPolicy) -> None:
        model = self._session.get(UserProfileModel, profile.id)
        if model is None:
            model = UserProfileModel(id=profile.id)
            self._session.add(model)

        model.market = profile.market.value
        model.holding_horizon = profile.holding_horizon.value
        model.risk_level = profile.risk_level.value
        model.single_position_limit = profile.single_position_limit
        model.notification_time = profile.notification_time
        model.created_at = profile.created_at
        model.updated_at = profile.updated_at

        # No ORM relationship is defined intentionally; flush the parent explicitly so
        # PostgreSQL can enforce the immutable policy's foreign key in the same transaction.
        self._session.flush()

        self._session.add(
            RiskPolicyVersionModel(
                id=policy.id,
                profile_id=policy.profile_id,
                version=policy.version,
                max_single_position=policy.max_single_position,
                live_trading_enabled=policy.live_trading_enabled,
                new_rule_confirmation_required=policy.new_rule_confirmation_required,
                created_at=policy.created_at,
            )
        )


class SqlAlchemyUnitOfWork(AbstractContextManager["SqlAlchemyUnitOfWork"]):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        self.profiles = SqlAlchemyProfileRepository(self.session)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()


def uow_factory(session_factory: sessionmaker[Session]):
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    return factory


def _profile_from_model(model: UserProfileModel) -> UserProfile:
    return UserProfile(
        id=model.id,
        market=Market(model.market),
        holding_horizon=HoldingHorizon(model.holding_horizon),
        risk_level=RiskLevel(model.risk_level),
        single_position_limit=Decimal(model.single_position_limit),
        notification_time=model.notification_time,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _policy_from_model(model: RiskPolicyVersionModel) -> RiskPolicy:
    return RiskPolicy(
        id=model.id,
        profile_id=model.profile_id,
        version=model.version,
        max_single_position=Decimal(model.max_single_position),
        live_trading_enabled=model.live_trading_enabled,
        new_rule_confirmation_required=model.new_rule_confirmation_required,
        created_at=_utc(model.created_at),
    )


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
