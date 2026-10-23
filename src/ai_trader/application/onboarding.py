from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from ai_trader.application.ports import UnitOfWorkFactory
from ai_trader.domain.profile import (
    HoldingHorizon,
    Market,
    RiskLevel,
    RiskPolicy,
    UserProfile,
    build_risk_policy,
)


@dataclass(frozen=True, slots=True)
class CompleteOnboarding:
    holding_horizon: HoldingHorizon
    risk_level: RiskLevel
    single_position_limit: Decimal | None
    notification_time: str
    market: Market = Market.A_SHARE


@dataclass(frozen=True, slots=True)
class OnboardingResult:
    profile: UserProfile
    policy: RiskPolicy
    changed: bool


class CompleteOnboardingHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def __call__(self, command: CompleteOnboarding) -> OnboardingResult:
        now = datetime.now(UTC)
        with self._uow_factory() as uow:
            existing = uow.profiles.get()
            current_policy = uow.profiles.current_policy()
            profile_id = existing.id if existing else uuid4()
            candidate_limit = command.single_position_limit
            policy = build_risk_policy(
                profile_id=profile_id,
                risk_level=command.risk_level,
                requested_limit=candidate_limit,
                version=(current_policy.version + 1) if current_policy else 1,
                now=now,
            )
            profile = UserProfile(
                id=profile_id,
                market=command.market,
                holding_horizon=command.holding_horizon,
                risk_level=command.risk_level,
                single_position_limit=policy.max_single_position,
                notification_time=command.notification_time,
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )

            if existing and current_policy and _same_profile(existing, profile):
                return OnboardingResult(existing, current_policy, changed=False)

            uow.profiles.save(profile, policy)
            return OnboardingResult(profile, policy, changed=True)


def _same_profile(left: UserProfile, right: UserProfile) -> bool:
    return (
        left.market == right.market
        and left.holding_horizon == right.holding_horizon
        and left.risk_level == right.risk_level
        and left.single_position_limit == right.single_position_limit
        and left.notification_time == right.notification_time
    )

