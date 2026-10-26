from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class TradeStatus(StrEnum):
    NORMAL = "normal"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


class AvailabilityBasis(StrEnum):
    PROVIDER_REPORTED = "provider_reported"
    CONSERVATIVE_POLICY = "conservative_policy"
    UNKNOWN = "unknown"


class VolumeUnit(StrEnum):
    SHARES = "shares"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DailyBar:
    instrument_id: str
    trading_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    previous_close: Decimal | None
    volume: Decimal
    volume_unit: VolumeUnit
    volume_resolution: Decimal
    turnover: Decimal
    trade_status: TradeStatus
    is_st: bool | None
    available_at: datetime
    availability_basis: AvailabilityBasis
    provider: str
    source_revision: str
    ingested_at: datetime


@dataclass(frozen=True, slots=True)
class TradeCalendarDay:
    calendar_date: date
    is_trading_day: bool
    provider: str
    ingested_at: datetime


@dataclass(frozen=True, slots=True)
class AdjustmentFactor:
    instrument_id: str
    effective_date: date
    forward_factor: Decimal
    backward_factor: Decimal
    raw_factor: Decimal
    provider: str
    source_revision: str
    ingested_at: datetime

