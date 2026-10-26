import socket
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from importlib.metadata import version
from threading import Lock
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


class MarketDataProviderError(RuntimeError):
    pass


class BaoStockMarketDataProvider:
    """Free A-share daily market-data adapter.

    Raw prices are requested without adjustment. Adjustment factors are loaded
    separately so downstream research can reproduce the chosen adjustment policy.
    """

    _BAR_FIELDS = (
        "date,code,open,high,low,close,preclose,volume,amount,"
        "adjustflag,tradestatus,isST"
    )

    _socket_lock = Lock()

    def __init__(self, client: ModuleType | Any | None = None, timeout_seconds: float = 15) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("BaoStock 超时必须在 0 到 60 秒之间")
        if client is None:
            import baostock as client_module

            client = client_module
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._source_revision = f"baostock-python-{version('baostock')}"

    def status(self) -> ProviderStatus:
        return ProviderStatus(configured=True, message="BaoStock 免费日线适配器已配置")

    def fetch_daily_bars(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[DailyBar, ...]:
        _validate_range(start, end)
        provider_code = _to_provider_code(instrument_id)
        ingested_at = datetime.now(UTC)
        with self._session():
            result = self._client.query_history_k_data_plus(
                provider_code,
                self._BAR_FIELDS,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                frequency="d",
                adjustflag="3",
            )
            rows = _read_result(result)

        bars = []
        for row in rows:
            trading_date = date.fromisoformat(row["date"])
            trade_status = _trade_status(row.get("tradestatus"))
            bars.append(
                DailyBar(
                    instrument_id=_to_instrument_id(row["code"]),
                    trading_date=trading_date,
                    open=_decimal_or_none(row.get("open")),
                    high=_decimal_or_none(row.get("high")),
                    low=_decimal_or_none(row.get("low")),
                    close=_decimal_or_none(row.get("close")),
                    previous_close=_decimal_or_none(row.get("preclose")),
                    volume=_decimal_or_zero(row.get("volume")),
                    volume_unit=VolumeUnit.SHARES,
                    volume_resolution=Decimal(1),
                    turnover=_decimal_or_zero(row.get("amount")),
                    trade_status=trade_status,
                    is_st=_bool_or_none(row.get("isST")),
                    available_at=_conservative_available_at(trading_date),
                    availability_basis=AvailabilityBasis.CONSERVATIVE_POLICY,
                    provider="baostock",
                    source_revision=self._source_revision,
                    ingested_at=ingested_at,
                )
            )
        return tuple(bars)

    def fetch_trade_calendar(
        self, *, start: date, end: date
    ) -> tuple[TradeCalendarDay, ...]:
        _validate_range(start, end)
        ingested_at = datetime.now(UTC)
        with self._session():
            rows = _read_result(
                self._client.query_trade_dates(
                    start_date=start.isoformat(), end_date=end.isoformat()
                )
            )
        return tuple(
            TradeCalendarDay(
                calendar_date=date.fromisoformat(row["calendar_date"]),
                is_trading_day=row["is_trading_day"] == "1",
                provider="baostock",
                ingested_at=ingested_at,
            )
            for row in rows
        )

    def fetch_adjustment_factors(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[AdjustmentFactor, ...]:
        _validate_range(start, end)
        provider_code = _to_provider_code(instrument_id)
        ingested_at = datetime.now(UTC)
        with self._session():
            rows = _read_result(
                self._client.query_adjust_factor(
                    provider_code,
                    # A dataset needs the factor already effective at its first
                    # trading day, even when no corporate action occurs inside
                    # the requested interval.
                    start_date="1990-01-01",
                    end_date=end.isoformat(),
                )
            )
        factors = tuple(
            AdjustmentFactor(
                instrument_id=_to_instrument_id(row["code"]),
                effective_date=date.fromisoformat(row["dividOperateDate"]),
                forward_factor=Decimal(row["foreAdjustFactor"]),
                backward_factor=Decimal(row["backAdjustFactor"]),
                raw_factor=Decimal(row["adjustFactor"]),
                provider="baostock",
                source_revision=self._source_revision,
                ingested_at=ingested_at,
            )
            for row in rows
        )
        baseline = max(
            (factor for factor in factors if factor.effective_date < start),
            key=lambda factor: factor.effective_date,
            default=None,
        )
        in_range = tuple(factor for factor in factors if start <= factor.effective_date <= end)
        return ((baseline,) if baseline else ()) + in_range

    def fetch_instrument_metadata(self, *, instrument_id: str) -> InstrumentMetadata:
        provider_code = _to_provider_code(instrument_id)
        ingested_at = datetime.now(UTC)
        with self._session():
            rows = _read_result(self._client.query_stock_basic(code=provider_code))
        if len(rows) != 1:
            raise MarketDataProviderError(
                f"BaoStock 证券主数据应返回 1 行，实际返回 {len(rows)} 行：{instrument_id}"
            )
        row = rows[0]
        instrument_types = {
            "1": InstrumentType.EQUITY,
            "2": InstrumentType.INDEX,
            "3": InstrumentType.OTHER,
        }
        instrument_type = instrument_types.get(row.get("type", ""))
        if instrument_type is None:
            raise MarketDataProviderError(
                f"BaoStock 返回未知证券类型：{row.get('type', '')} ({instrument_id})"
            )
        return InstrumentMetadata(
            instrument_id=_to_instrument_id(row["code"]),
            instrument_type=instrument_type,
            listed_on=_date_or_none(row.get("ipoDate")),
            delisted_on=_date_or_none(row.get("outDate")),
            provider="baostock",
            source_revision=self._source_revision,
            ingested_at=ingested_at,
        )

    @contextmanager
    def _session(self) -> Iterator[None]:
        # BaoStock 0.9.x does not expose connect/read timeouts and uses one
        # process-global socket. Serialize access while applying a bounded
        # default timeout, then restore the caller's socket policy.
        with self._socket_lock:
            previous_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(self._timeout_seconds)
            try:
                login = self._client.login()
                _raise_on_error(login, "登录")
                try:
                    yield
                finally:
                    self._client.logout()
            finally:
                socket.setdefaulttimeout(previous_timeout)


def _read_result(result: Any) -> tuple[dict[str, str], ...]:
    _raise_on_error(result, "查询")
    fields = tuple(result.fields)
    rows: list[dict[str, str]] = []
    while result.next():
        rows.append(dict(zip(fields, result.get_row_data(), strict=True)))
    return tuple(rows)


def _raise_on_error(result: Any, operation: str) -> None:
    if str(result.error_code) != "0":
        raise MarketDataProviderError(
            f"BaoStock {operation}失败：{result.error_code} {result.error_msg}"
        )


def _validate_range(start: date, end: date) -> None:
    if end < start:
        raise ValueError("行情结束日期不能早于开始日期")


def _to_provider_code(instrument_id: str) -> str:
    try:
        code, exchange = instrument_id.split(".")
    except ValueError as error:
        raise ValueError("证券代码必须使用 600000.XSHG 格式") from error
    prefixes = {"XSHG": "sh", "XSHE": "sz", "BJSE": "bj"}
    if exchange not in prefixes or len(code) != 6 or not code.isdigit():
        raise ValueError("证券代码必须使用 600000.XSHG、000001.XSHE 或 920000.BJSE 格式")
    return f"{prefixes[exchange]}.{code}"


def _to_instrument_id(provider_code: str) -> str:
    exchange, code = provider_code.lower().split(".")
    suffixes = {"sh": "XSHG", "sz": "XSHE", "bj": "BJSE"}
    if exchange not in suffixes:
        raise MarketDataProviderError(f"BaoStock 返回未知交易所代码：{provider_code}")
    return f"{code}.{suffixes[exchange]}"


def _trade_status(value: str | None) -> TradeStatus:
    if value == "1":
        return TradeStatus.NORMAL
    if value == "0":
        return TradeStatus.SUSPENDED
    return TradeStatus.UNKNOWN


def _bool_or_none(value: str | None) -> bool | None:
    if value == "1":
        return True
    if value == "0":
        return False
    return None


def _decimal_or_none(value: str | None) -> Decimal | None:
    return Decimal(value) if value not in (None, "") else None


def _decimal_or_zero(value: str | None) -> Decimal:
    return Decimal(value) if value not in (None, "") else Decimal(0)


def _date_or_none(value: str | None) -> date | None:
    return date.fromisoformat(value) if value not in (None, "") else None


def _conservative_available_at(trading_date: date) -> datetime:
    shanghai = ZoneInfo("Asia/Shanghai")
    next_midnight = datetime.combine(trading_date + timedelta(days=1), time.min, shanghai)
    return next_midnight.astimezone(UTC)
