import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import StrEnum
from zoneinfo import ZoneInfo

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


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    code: str
    severity: IssueSeverity
    message: str
    instrument_id: str | None = None
    trading_date: str | None = None


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    accepted: bool
    row_count: int
    instrument_count: int
    trading_day_count: int
    coverage_ratio: Decimal | None
    issues: tuple[DataQualityIssue, ...]


_INSTRUMENT_PATTERN = re.compile(r"^\d{6}\.(XSHG|XSHE|BJSE)$")


def validate_daily_bars(
    bars: Iterable[DailyBar],
    calendar: Iterable[TradeCalendarDay] | None = None,
    factors: Iterable[AdjustmentFactor] | None = None,
    instruments: Iterable[InstrumentMetadata] | None = None,
) -> DataQualityReport:
    rows = tuple(bars)
    calendar_rows = tuple(calendar or ())
    factor_rows = tuple(factors) if factors is not None else None
    instrument_rows = tuple(instruments) if instruments is not None else None
    issues: list[DataQualityIssue] = []
    seen: set[tuple[str, object]] = set()

    instrument_index: dict[str, InstrumentMetadata] = {}
    if instrument_rows is not None:
        for instrument in instrument_rows:
            if instrument.instrument_id in instrument_index:
                issues.append(
                    DataQualityIssue(
                        "duplicate_instrument_metadata",
                        IssueSeverity.ERROR,
                        "证券主数据重复",
                        instrument_id=instrument.instrument_id,
                    )
                )
            instrument_index[instrument.instrument_id] = instrument
            if (
                instrument.listed_on is not None
                and instrument.delisted_on is not None
                and instrument.delisted_on < instrument.listed_on
            ):
                issues.append(
                    DataQualityIssue(
                        "invalid_listing_window",
                        IssueSeverity.ERROR,
                        "退市日期早于上市日期",
                        instrument_id=instrument.instrument_id,
                    )
                )

    if not rows:
        issues.append(
            DataQualityIssue("empty_dataset", IssueSeverity.ERROR, "行情数据集为空")
        )

    trading_dates = {day.calendar_date for day in calendar_rows if day.is_trading_day}
    for bar in rows:
        key = (bar.instrument_id, bar.trading_date)
        if key in seen:
            issues.append(_issue("duplicate_bar", "证券与交易日重复", bar))
        seen.add(key)

        if not _INSTRUMENT_PATTERN.fullmatch(bar.instrument_id):
            issues.append(_issue("invalid_instrument", "证券代码不是规范格式", bar))
        metadata = instrument_index.get(bar.instrument_id)
        if instrument_rows is not None and metadata is None:
            issues.append(_issue("missing_instrument_metadata", "证券缺少主数据", bar))
        elif metadata is not None:
            if metadata.listed_on is not None and bar.trading_date < metadata.listed_on:
                issues.append(_issue("before_listing", "日线早于上市日期", bar))
            if metadata.delisted_on is not None and bar.trading_date > metadata.delisted_on:
                issues.append(_issue("after_delisting", "日线晚于退市日期", bar))
        if trading_dates and bar.trading_date not in trading_dates:
            issues.append(_issue("non_trading_day", "日线日期不在交易日历中", bar))
        if bar.volume < 0 or bar.turnover < 0:
            issues.append(_issue("negative_activity", "成交量或成交额小于零", bar))
        if bar.volume_unit is not VolumeUnit.SHARES:
            issues.append(_issue("unknown_volume_unit", "成交量未规范为股", bar))
        if bar.volume_resolution <= 0:
            issues.append(_issue("invalid_volume_resolution", "成交量精度必须为正数", bar))
        if bar.available_at.tzinfo is None:
            issues.append(_issue("naive_available_at", "可用时间缺少时区", bar))
        else:
            market_close = datetime.combine(
                bar.trading_date, time(15), ZoneInfo("Asia/Shanghai")
            ).astimezone(UTC)
            if bar.available_at.astimezone(UTC) < market_close:
                issues.append(_issue("future_leakage", "日线在当日收盘前已标记可用", bar))
        if bar.availability_basis is AvailabilityBasis.UNKNOWN:
            issues.append(_issue("unknown_availability", "无法证明数据的可用时点", bar))

        prices = (bar.open, bar.high, bar.low, bar.close)
        if bar.trade_status is TradeStatus.NORMAL:
            if any(value is None or value <= 0 for value in prices):
                issues.append(_issue("invalid_price", "正常交易日价格必须为正数", bar))
            elif bar.high < max(bar.open, bar.low, bar.close):
                issues.append(_issue("invalid_high", "最高价低于开盘、最低或收盘价", bar))
            elif bar.low > min(bar.open, bar.high, bar.close):
                issues.append(_issue("invalid_low", "最低价高于开盘、最高或收盘价", bar))
        elif bar.trade_status is TradeStatus.SUSPENDED and (
            bar.volume != 0 or bar.turnover != 0
        ):
            issues.append(_issue("suspended_with_activity", "停牌日存在成交活动", bar))
        elif bar.trade_status is TradeStatus.UNKNOWN:
            issues.append(_issue("unknown_trade_status", "交易状态未知", bar))

    bar_instrument_ids = {bar.instrument_id for bar in rows}
    instrument_ids = (
        set(instrument_index) if instrument_rows is not None else bar_instrument_ids
    )
    observed_dates = {bar.trading_date for bar in rows}
    coverage_ratio: Decimal | None = None
    if trading_dates and instrument_ids:
        expected_keys = {
            (instrument_id, trading_date)
            for instrument_id in instrument_ids
            for trading_date in trading_dates
            if _inside_listing_window(instrument_index.get(instrument_id), trading_date)
        }
        expected = len(expected_keys)
        covered = len(seen & expected_keys)
        coverage_ratio = Decimal(covered) / Decimal(expected) if expected else None
        if coverage_ratio is not None and coverage_ratio < Decimal("0.98"):
            issues.append(
                DataQualityIssue(
                    "insufficient_coverage",
                    IssueSeverity.ERROR,
                    f"交易日覆盖率 {coverage_ratio:.2%} 低于 98%",
                )
            )

    if factor_rows is not None:
        factor_instruments = {factor.instrument_id for factor in factor_rows}
        factor_required = {
            instrument_id
            for instrument_id in instrument_ids
            if instrument_index.get(instrument_id) is None
            or instrument_index[instrument_id].instrument_type is InstrumentType.EQUITY
        }
        for instrument_id in sorted(factor_required - factor_instruments):
            issues.append(
                DataQualityIssue(
                    "missing_adjustment_factor",
                    IssueSeverity.ERROR,
                    "证券缺少独立复权因子",
                    instrument_id=instrument_id,
                )
            )
        earliest_bar_dates = {
            instrument_id: min(
                bar.trading_date for bar in rows if bar.instrument_id == instrument_id
            )
            for instrument_id in bar_instrument_ids
        }
        for instrument_id in sorted(
            factor_required & factor_instruments & bar_instrument_ids
        ):
            if not any(
                factor.instrument_id == instrument_id
                and factor.effective_date <= earliest_bar_dates[instrument_id]
                for factor in factor_rows
            ):
                issues.append(
                    DataQualityIssue(
                        "missing_baseline_adjustment_factor",
                        IssueSeverity.ERROR,
                        "首个交易日前缺少已生效的基准复权因子",
                        instrument_id=instrument_id,
                    )
                )
        factor_keys = set()
        for factor in factor_rows:
            key = (factor.instrument_id, factor.effective_date)
            if key in factor_keys:
                issues.append(
                    DataQualityIssue(
                        "duplicate_adjustment_factor",
                        IssueSeverity.ERROR,
                        "复权因子日期重复",
                        instrument_id=factor.instrument_id,
                        trading_date=factor.effective_date.isoformat(),
                    )
                )
            factor_keys.add(key)
            if min(factor.forward_factor, factor.backward_factor, factor.raw_factor) <= 0:
                issues.append(
                    DataQualityIssue(
                        "invalid_adjustment_factor",
                        IssueSeverity.ERROR,
                        "复权因子必须为正数",
                        instrument_id=factor.instrument_id,
                        trading_date=factor.effective_date.isoformat(),
                    )
                )

    return DataQualityReport(
        accepted=not any(issue.severity is IssueSeverity.ERROR for issue in issues),
        row_count=len(rows),
        instrument_count=len(instrument_ids),
        trading_day_count=len(observed_dates),
        coverage_ratio=coverage_ratio,
        issues=tuple(issues),
    )


def _issue(code: str, message: str, bar: DailyBar) -> DataQualityIssue:
    return DataQualityIssue(
        code=code,
        severity=IssueSeverity.ERROR,
        message=message,
        instrument_id=bar.instrument_id,
        trading_date=bar.trading_date.isoformat(),
    )


def _inside_listing_window(
    instrument: InstrumentMetadata | None, trading_date: date
) -> bool:
    if instrument is None:
        return True
    return not (
        (instrument.listed_on is not None and trading_date < instrument.listed_on)
        or (instrument.delisted_on is not None and trading_date > instrument.delisted_on)
    )
