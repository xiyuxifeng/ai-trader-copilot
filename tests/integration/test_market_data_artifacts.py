from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl

from ai_trader.domain.market_data import (
    AdjustmentFactor,
    AvailabilityBasis,
    DailyBar,
    TradeCalendarDay,
    TradeStatus,
    VolumeUnit,
)
from ai_trader.infrastructure.market_data.dataset import MarketDatasetWriter
from ai_trader.maintenance.market_inventory import inspect_market_data


def test_writes_checksum_manifest_and_parquet(tmp_path: Path) -> None:
    bar = _bar()
    calendar = (
        TradeCalendarDay(
            calendar_date=bar.trading_date,
            is_trading_day=True,
            provider="fixture",
            ingested_at=bar.ingested_at,
        ),
    )
    factors = (
        AdjustmentFactor(
            instrument_id=bar.instrument_id,
            effective_date=bar.trading_date,
            forward_factor=Decimal("1"),
            backward_factor=Decimal("1"),
            raw_factor=Decimal("1"),
            provider="fixture",
            source_revision="fixture-v1",
            ingested_at=bar.ingested_at,
        ),
    )
    manifest = MarketDatasetWriter().write(
        target_root=tmp_path,
        bars=(bar,),
        calendar=calendar,
        factors=factors,
    )

    dataset_path = tmp_path / manifest.dataset_id
    assert (dataset_path / "manifest.json").is_file()
    assert (dataset_path / "quality_report.json").is_file()
    assert pl.read_parquet(dataset_path / "daily_bars.parquet").height == 1
    assert all(len(item.sha256) == 64 for item in manifest.files)


def test_inventory_reports_structure_without_raw_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "daily.csv"
    pl.DataFrame(
        {
            "code": ["sh.600000", "sh.600000"],
            "date": ["2024-01-02", "2024-01-03"],
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10.5, 11.5],
            "volume": [100, 200],
        }
    ).write_csv(csv_path)

    report = inspect_market_data(tmp_path)

    assert report.file_count == 1
    assert report.files[0].rows == 2
    assert report.files[0].symbol_count == 1
    assert report.files[0].minimum_date == "2024-01-02"
    assert "未识别复权字段或复权因子" in report.files[0].warnings
    assert not hasattr(report.files[0], "sample_rows")


def _bar() -> DailyBar:
    return DailyBar(
        instrument_id="600000.XSHG",
        trading_date=date(2024, 1, 2),
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9.5"),
        close=Decimal("10.5"),
        previous_close=Decimal("9.8"),
        volume=Decimal("1000"),
        volume_unit=VolumeUnit.SHARES,
        volume_resolution=Decimal("1"),
        turnover=Decimal("10200"),
        trade_status=TradeStatus.NORMAL,
        is_st=False,
        available_at=datetime(2024, 1, 2, 16, tzinfo=UTC),
        availability_basis=AvailabilityBasis.CONSERVATIVE_POLICY,
        provider="fixture",
        source_revision="fixture-v1",
        ingested_at=datetime(2024, 1, 3, tzinfo=UTC),
    )
