from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4


class Market(StrEnum):
    A_SHARE = "a_share"


class HoldingHorizon(StrEnum):
    SHORT = "short"
    SWING = "swing"
    LONG = "long"


class RiskLevel(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


_POSITION_LIMITS = {
    RiskLevel.CONSERVATIVE: Decimal("0.10"),
    RiskLevel.BALANCED: Decimal("0.20"),
    RiskLevel.AGGRESSIVE: Decimal("0.30"),
}


@dataclass(frozen=True, slots=True)
class UserProfile:
    id: UUID
    market: Market
    holding_horizon: HoldingHorizon
    risk_level: RiskLevel
    single_position_limit: Decimal
    notification_time: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    id: UUID
    profile_id: UUID
    version: int
    max_single_position: Decimal
    live_trading_enabled: bool
    new_rule_confirmation_required: bool
    created_at: datetime


def recommended_position_limit(risk_level: RiskLevel) -> Decimal:
    return _POSITION_LIMITS[risk_level]


def build_risk_policy(
    *,
    profile_id: UUID,
    risk_level: RiskLevel,
    requested_limit: Decimal | None,
    version: int,
    now: datetime | None = None,
) -> RiskPolicy:
    limit = requested_limit or recommended_position_limit(risk_level)
    if limit < Decimal("0.05") or limit > Decimal("0.50"):
        raise ValueError("单只股票最大仓位必须在 5% 到 50% 之间")
    if limit.as_tuple().exponent < -2:
        raise ValueError("单只股票最大仓位最多保留两位小数")

    return RiskPolicy(
        id=uuid4(),
        profile_id=profile_id,
        version=version,
        max_single_position=limit,
        live_trading_enabled=False,
        new_rule_confirmation_required=True,
        created_at=now or datetime.now(UTC),
    )

