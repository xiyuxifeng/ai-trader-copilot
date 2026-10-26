import math
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from importlib.metadata import version
from types import ModuleType
from typing import Any
from zoneinfo import ZoneInfo

from ai_trader.application.provider_ports import ProviderStatus
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


class AKShareMarketDataProvider:
    """Free Eastmoney/Sina-backed candidate adapter used for P0 comparison.

    AKShare's A-share history endpoint does not expose an independent adjustment
    factor or explicit suspension flag. The adapter therefore returns no factors;
    the shared quality gate must reject it as a standalone publishable dataset.
    """

    def __init__(self, client: ModuleType | Any | None = None, timeout_seconds: float = 15) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("AKShare 超时必须在 0 到 60 秒之间")
        if client is None:
            import akshare as client_module

            client = client_module
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._source_revision = f"akshare-{version('akshare')}:stock_zh_a_hist"

    def status(self) -> ProviderStatus:
        return ProviderStatus(configured=True, message="AKShare 免费日线候选适配器已配置")

    def fetch_daily_bars(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[DailyBar, ...]:
        _validate_range(start, end)
        symbol = _symbol(instrument_id)
        frame = self._client.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="",
            timeout=self._timeout_seconds,
        )
        ingested_at = datetime.now(UTC)
        rows = []
        for record in frame.to_dict(orient="records"):
            volume_lots = _required_decimal(record.get("成交量"), "成交量")
            volume_shares = volume_lots * Decimal(100)
            rows.append(
                DailyBar(
                    instrument_id=instrument_id,
                    trading_date=_date(record["日期"]),
                    open=_optional_decimal(record.get("开盘")),
                    high=_optional_decimal(record.get("最高")),
                    low=_optional_decimal(record.get("最低")),
                    close=_optional_decimal(record.get("收盘")),
                    previous_close=None,
                    volume=volume_shares,
                    volume_unit=VolumeUnit.SHARES,
                    volume_resolution=Decimal(100),
                    turnover=_required_decimal(record.get("成交额"), "成交额"),
                    trade_status=(
                        TradeStatus.NORMAL if volume_shares > 0 else TradeStatus.UNKNOWN
                    ),
                    is_st=None,
                    available_at=_conservative_available_at(_date(record["日期"])),
                    availability_basis=AvailabilityBasis.CONSERVATIVE_POLICY,
                    provider="akshare-eastmoney",
                    source_revision=self._source_revision,
                    ingested_at=ingested_at,
                )
            )
        return tuple(rows)

    def fetch_trade_calendar(
        self, *, start: date, end: date
    ) -> tuple[TradeCalendarDay, ...]:
        _validate_range(start, end)
        frame = self._client.tool_trade_date_hist_sina()
        ingested_at = datetime.now(UTC)
        dates = (_date(record["trade_date"]) for record in frame.to_dict(orient="records"))
        return tuple(
            TradeCalendarDay(
                calendar_date=calendar_date,
                is_trading_day=True,
                provider="akshare-sina",
                ingested_at=ingested_at,
            )
            for calendar_date in dates
            if start <= calendar_date <= end
        )

    def fetch_adjustment_factors(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[AdjustmentFactor, ...]:
        _validate_range(start, end)
        _symbol(instrument_id)
        return ()

    def fetch_instrument_metadata(self, *, instrument_id: str) -> InstrumentMetadata:
        _symbol(instrument_id)
        return InstrumentMetadata(
            instrument_id=instrument_id,
            instrument_type=InstrumentType.EQUITY,
            listed_on=None,
            delisted_on=None,
            provider="akshare-eastmoney",
            source_revision=self._source_revision,
            ingested_at=datetime.now(UTC),
        )


def _symbol(instrument_id: str) -> str:
    try:
        code, exchange = instrument_id.split(".")
    except ValueError as error:
        raise ValueError("证券代码必须使用 600000.XSHG 格式") from error
    if exchange not in {"XSHG", "XSHE"} or len(code) != 6 or not code.isdigit():
        raise ValueError("AKShare 候选适配器当前只验证沪深六位证券代码")
    if (exchange == "XSHG" and code.startswith("000")) or (
        exchange == "XSHE" and code.startswith("399")
    ):
        raise ValueError("AKShare 股票接口不能用于指数代码；指数候选源尚未通过 P0 验证")
    return code


def _validate_range(start: date, end: date) -> None:
    if end < start:
        raise ValueError("行情结束日期不能早于开始日期")


def _date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return Decimal(str(value))


def _required_decimal(value: object, field: str) -> Decimal:
    parsed = _optional_decimal(value)
    if parsed is None:
        raise ValueError(f"AKShare 返回空的{field}")
    return parsed


def _conservative_available_at(trading_date: date) -> datetime:
    shanghai = ZoneInfo("Asia/Shanghai")
    next_midnight = datetime.combine(trading_date + timedelta(days=1), time.min, shanghai)
    return next_midnight.astimezone(UTC)
