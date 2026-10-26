from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from ai_trader.domain.market_data import AdjustmentFactor, DailyBar, TradeCalendarDay


class ProviderNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    configured: bool
    message: str


class LLMProvider(Protocol):
    def status(self) -> ProviderStatus: ...

    def generate_structured(
        self,
        *,
        task: str,
        payload: dict[str, object],
    ) -> dict[str, object]: ...


class MarketDataProvider(Protocol):
    def status(self) -> ProviderStatus: ...

    def fetch_daily_bars(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[DailyBar, ...]: ...

    def fetch_trade_calendar(
        self, *, start: date, end: date
    ) -> tuple[TradeCalendarDay, ...]: ...

    def fetch_adjustment_factors(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[AdjustmentFactor, ...]: ...


class ArticleSourceAdapter(Protocol):
    def load(self, request: dict[str, object]) -> dict[str, object]: ...


class NotificationProvider(Protocol):
    def send(self, *, subject: str, body: str, deliver_after: datetime | None = None) -> None: ...


class UnconfiguredLLMProvider:
    def status(self) -> ProviderStatus:
        return ProviderStatus(configured=False, message="AI 服务尚未配置")

    def generate_structured(self, *, task: str, payload: dict[str, object]) -> dict[str, object]:
        raise ProviderNotConfigured("AI 服务尚未配置")


class UnconfiguredMarketDataProvider:
    def status(self) -> ProviderStatus:
        return ProviderStatus(configured=False, message="行情服务尚未配置")

    def fetch_daily_bars(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[DailyBar, ...]:
        raise ProviderNotConfigured("行情服务尚未配置")

    def fetch_trade_calendar(
        self, *, start: date, end: date
    ) -> tuple[TradeCalendarDay, ...]:
        raise ProviderNotConfigured("行情服务尚未配置")

    def fetch_adjustment_factors(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[AdjustmentFactor, ...]:
        raise ProviderNotConfigured("行情服务尚未配置")
