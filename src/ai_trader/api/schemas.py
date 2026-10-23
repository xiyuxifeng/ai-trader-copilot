from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_trader.domain.profile import HoldingHorizon, Market, RiskLevel


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: Market = Market.A_SHARE
    holding_horizon: HoldingHorizon
    risk_level: RiskLevel
    single_position_limit: Decimal | None = Field(
        default=None,
        ge=Decimal("0.05"),
        le=Decimal("0.50"),
    )
    notification_time: str = "18:30"

    @field_validator("notification_time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        try:
            hour, minute = (int(part) for part in value.split(":"))
        except (ValueError, TypeError) as error:
            raise ValueError("提醒时间必须使用 HH:MM 格式") from error
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("提醒时间必须使用 HH:MM 格式")
        return f"{hour:02d}:{minute:02d}"


class ProfileResponse(BaseModel):
    id: UUID
    market: Market
    holding_horizon: HoldingHorizon
    risk_level: RiskLevel
    single_position_limit: Decimal
    notification_time: str
    risk_policy_version: int
    live_trading_enabled: Literal[False] = False
    updated_at: datetime


class OnboardingResponse(BaseModel):
    profile: ProfileResponse
    changed: bool


class TodayResponse(BaseModel):
    setup_required: bool
    market_summary: str
    data_as_of: date | None
    positions_message: str
    candidates_message: str
    exceptions_count: int
    learning_message: str


class ComponentHealth(BaseModel):
    status: Literal["ok", "unavailable", "not_configured"]
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: ComponentHealth
    worker: ComponentHealth
    market_data: ComponentHealth
    ai_service: ComponentHealth
