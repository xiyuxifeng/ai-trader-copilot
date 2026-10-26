from datetime import UTC, date, datetime
from decimal import Decimal

from ai_trader.application.market_data_quality import validate_daily_bars
from ai_trader.domain.market_data import (
    AdjustmentFactor,
    AvailabilityBasis,
    DailyBar,
    TradeCalendarDay,
    TradeStatus,
    VolumeUnit,
)


def test_accepts_complete_daily_bars_with_conservative_availability() -> None:
    bars = (_bar(),)
    calendar = (
        TradeCalendarDay(
            calendar_date=date(2024, 1, 2),
            is_trading_day=True,
            provider="fixture",
            ingested_at=datetime(2024, 1, 3, tzinfo=UTC),
        ),
    )

    report = validate_daily_bars(bars, calendar)

    assert report.accepted is True
    assert report.coverage_ratio == Decimal("1")
    assert report.issues == ()


def test_blocks_unknown_availability_and_missing_calendar_coverage() -> None:
    bar = _bar(
        available_at=datetime(2024, 1, 2, 6, tzinfo=UTC),
        availability_basis=AvailabilityBasis.UNKNOWN,
    )
    calendar = tuple(
        TradeCalendarDay(
            calendar_date=day,
            is_trading_day=True,
            provider="fixture",
            ingested_at=datetime(2024, 1, 4, tzinfo=UTC),
        )
        for day in (date(2024, 1, 2), date(2024, 1, 3))
    )

    report = validate_daily_bars((bar,), calendar)

    assert report.accepted is False
    assert {issue.code for issue in report.issues} == {
        "future_leakage",
        "unknown_availability",
        "insufficient_coverage",
    }


def test_blocks_invalid_ohlc_and_suspended_volume() -> None:
    invalid_price = _bar(high=Decimal("9"))
    invalid_suspension = _bar(
        instrument_id="000001.XSHE",
        trade_status=TradeStatus.SUSPENDED,
        volume=Decimal("1"),
    )

    report = validate_daily_bars((invalid_price, invalid_suspension))

    assert report.accepted is False
    assert {issue.code for issue in report.issues} == {"invalid_high", "suspended_with_volume"}


def test_blocks_missing_independent_adjustment_factor() -> None:
    report = validate_daily_bars((_bar(),), factors=())

    assert report.accepted is False
    assert [issue.code for issue in report.issues] == ["missing_adjustment_factor"]


def test_blocks_factor_that_only_becomes_effective_after_first_bar() -> None:
    bar = _bar()
    factor = AdjustmentFactor(
        instrument_id=bar.instrument_id,
        effective_date=date(2024, 1, 3),
        forward_factor=Decimal("1"),
        backward_factor=Decimal("1"),
        raw_factor=Decimal("1"),
        provider="fixture",
        source_revision="fixture-v1",
        ingested_at=datetime(2024, 1, 4, tzinfo=UTC),
    )

    report = validate_daily_bars((bar,), factors=(factor,))

    assert report.accepted is False
    assert [issue.code for issue in report.issues] == [
        "missing_baseline_adjustment_factor"
    ]


def _bar(**overrides: object) -> DailyBar:
    values: dict[str, object] = {
        "instrument_id": "600000.XSHG",
        "trading_date": date(2024, 1, 2),
        "open": Decimal("10"),
        "high": Decimal("11"),
        "low": Decimal("9.5"),
        "close": Decimal("10.5"),
        "previous_close": Decimal("9.8"),
        "volume": Decimal("1000"),
        "volume_unit": VolumeUnit.SHARES,
        "volume_resolution": Decimal("1"),
        "turnover": Decimal("10200"),
        "trade_status": TradeStatus.NORMAL,
        "is_st": False,
        "available_at": datetime(2024, 1, 2, 16, tzinfo=UTC),
        "availability_basis": AvailabilityBasis.CONSERVATIVE_POLICY,
        "provider": "fixture",
        "source_revision": "fixture-v1",
        "ingested_at": datetime(2024, 1, 3, tzinfo=UTC),
    }
    values.update(overrides)
    return DailyBar(**values)  # type: ignore[arg-type]

