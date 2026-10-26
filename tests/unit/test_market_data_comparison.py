from datetime import UTC, date, datetime
from decimal import Decimal

from ai_trader.application.market_data_comparison import compare_daily_bars
from ai_trader.domain.market_data import (
    AvailabilityBasis,
    DailyBar,
    TradeStatus,
    VolumeUnit,
)


def test_compares_normalized_provider_rows_without_exposing_raw_rows() -> None:
    left = (_bar(),)
    right = (
        _bar(
            close=Decimal("10.51"),
            volume=Decimal("1050"),
            volume_resolution=Decimal("100"),
            turnover=Decimal("10200.5"),
        ),
    )

    report = compare_daily_bars(left, right)

    by_field = {field.field: field for field in report.fields}
    assert report.overlapping_rows == 1
    assert report.missing_from_left == 0
    assert by_field["close"].mismatches == 1
    assert by_field["close"].maximum_absolute_difference == Decimal("0.01")
    assert by_field["turnover_cny"].mismatches == 0
    assert by_field["volume_shares"].mismatches == 0
    assert by_field["volume_shares"].tolerance == Decimal("100")


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
