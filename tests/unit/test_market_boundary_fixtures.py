import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ai_trader.application.market_data_quality import validate_daily_bars
from ai_trader.domain.market_data import (
    AdjustmentFactor,
    AvailabilityBasis,
    DailyBar,
    InstrumentMetadata,
    InstrumentType,
    TradeCalendarDay,
    TradeStatus,
    VolumeUnit,
)

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "market_boundary_cases_v0.json"


def _cases() -> list[dict[str, object]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "market-boundary-cases-v0"
    return payload["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_market_boundary_fixture(case: dict[str, object]) -> None:
    instrument_payload = case["instrument"]
    assert isinstance(instrument_payload, dict)
    instrument_id = str(instrument_payload["id"])
    metadata = InstrumentMetadata(
        instrument_id=instrument_id,
        instrument_type=InstrumentType(str(instrument_payload["type"])),
        listed_on=_optional_date(instrument_payload.get("listed_on")),
        delisted_on=_optional_date(instrument_payload.get("delisted_on")),
        provider="fixture",
        source_revision="market-boundary-cases-v0",
        ingested_at=datetime(2026, 10, 26, tzinfo=UTC),
    )
    calendar = tuple(
        TradeCalendarDay(
            calendar_date=date.fromisoformat(str(day)),
            is_trading_day=True,
            provider="fixture",
            ingested_at=datetime(2026, 10, 26, tzinfo=UTC),
        )
        for day in case["calendar"]  # type: ignore[union-attr]
    )
    bars = tuple(
        _bar(instrument_id, row) for row in case["bars"]  # type: ignore[union-attr]
    )
    factor_payload = case.get("factors")
    factors = (
        tuple(_factor(instrument_id, row) for row in factor_payload)
        if isinstance(factor_payload, list)
        else None
    )

    report = validate_daily_bars(bars, calendar, factors, (metadata,))

    expected = case["expected"]
    assert isinstance(expected, dict)
    assert report.accepted is expected["accepted"]
    assert str(report.coverage_ratio) == expected["coverage_ratio"]
    assert [issue.code for issue in report.issues] == expected["issue_codes"]


def _bar(instrument_id: str, payload: object) -> DailyBar:
    assert isinstance(payload, dict)
    trading_date = date.fromisoformat(str(payload["date"]))
    available_at = payload.get("available_at")
    if available_at is None:
        shanghai = ZoneInfo("Asia/Shanghai")
        available = datetime.combine(
            trading_date + timedelta(days=1), time.min, shanghai
        ).astimezone(UTC)
    else:
        available = datetime.fromisoformat(str(available_at))
    return DailyBar(
        instrument_id=instrument_id,
        trading_date=trading_date,
        open=_decimal(payload.get("open", "10")),
        high=_decimal(payload.get("high", "11")),
        low=_decimal(payload.get("low", "9")),
        close=_decimal(payload.get("close", "10.5")),
        previous_close=_decimal(payload.get("previous_close", "10")),
        volume=Decimal(str(payload.get("volume", "1000"))),
        volume_unit=VolumeUnit.SHARES,
        volume_resolution=Decimal(1),
        turnover=Decimal(str(payload.get("turnover", "10000"))),
        trade_status=TradeStatus(str(payload.get("trade_status", "normal"))),
        is_st=bool(payload.get("is_st", False)),
        available_at=available,
        availability_basis=AvailabilityBasis.CONSERVATIVE_POLICY,
        provider="fixture",
        source_revision="market-boundary-cases-v0",
        ingested_at=datetime(2026, 10, 26, tzinfo=UTC),
    )


def _factor(instrument_id: str, payload: object) -> AdjustmentFactor:
    assert isinstance(payload, dict)
    return AdjustmentFactor(
        instrument_id=instrument_id,
        effective_date=date.fromisoformat(str(payload["effective_date"])),
        forward_factor=Decimal(str(payload["forward"])),
        backward_factor=Decimal(str(payload["backward"])),
        raw_factor=Decimal(str(payload["raw"])),
        provider="fixture",
        source_revision="market-boundary-cases-v0",
        ingested_at=datetime(2026, 10, 26, tzinfo=UTC),
    )


def _decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _optional_date(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))
