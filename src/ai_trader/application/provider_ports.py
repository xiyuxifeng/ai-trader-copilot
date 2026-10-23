from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


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
