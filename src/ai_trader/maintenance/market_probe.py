import argparse
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from ai_trader.application.market_data_quality import validate_daily_bars
from ai_trader.domain.market_data import (
    AdjustmentFactor,
    DailyBar,
    InstrumentMetadata,
    TradeCalendarDay,
    TradeStatus,
)
from ai_trader.infrastructure.market_data.akshare_provider import AKShareMarketDataProvider
from ai_trader.infrastructure.market_data.baostock_provider import BaoStockMarketDataProvider


class ProbeProvider(Protocol):
    def status(self): ...

    def fetch_daily_bars(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[DailyBar, ...]: ...

    def fetch_trade_calendar(
        self, *, start: date, end: date
    ) -> tuple[TradeCalendarDay, ...]: ...

    def fetch_adjustment_factors(
        self, *, instrument_id: str, start: date, end: date
    ) -> tuple[AdjustmentFactor, ...]: ...

    def fetch_instrument_metadata(self, *, instrument_id: str) -> InstrumentMetadata: ...


def run_probe(
    *, provider_name: str, instruments: tuple[str, ...], start: date, end: date
) -> dict[str, object]:
    provider: ProbeProvider
    if provider_name == "baostock":
        provider = BaoStockMarketDataProvider()
    elif provider_name == "akshare":
        provider = AKShareMarketDataProvider()
    else:
        raise ValueError(f"未知行情供应商：{provider_name}")
    instruments_metadata = tuple(
        provider.fetch_instrument_metadata(instrument_id=instrument_id)
        for instrument_id in instruments
    )
    calendar = provider.fetch_trade_calendar(start=start, end=end)
    bars = tuple(
        bar
        for instrument_id in instruments
        for bar in provider.fetch_daily_bars(
            instrument_id=instrument_id, start=start, end=end
        )
    )
    factors = tuple(
        factor
        for instrument_id in instruments
        for factor in provider.fetch_adjustment_factors(
            instrument_id=instrument_id, start=start, end=end
        )
    )
    report = validate_daily_bars(bars, calendar, factors, instruments_metadata)
    return {
        "schema_version": "market-provider-probe-v0",
        "provider": provider_name,
        "status": asdict(provider.status()),
        "request": {
            "instruments": instruments,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "observed": {
            "bar_rows": len(bars),
            "calendar_rows": len(calendar),
            "trading_days": sum(day.is_trading_day for day in calendar),
            "factor_rows": len(factors),
            "factor_events_in_range": sum(
                start <= factor.effective_date <= end for factor in factors
            ),
            "suspended_rows": sum(
                bar.trade_status is TradeStatus.SUSPENDED for bar in bars
            ),
            "st_rows": sum(bar.is_st is True for bar in bars),
            "instrument_metadata": [
                {
                    "instrument_id": item.instrument_id,
                    "instrument_type": item.instrument_type,
                    "listed_on": item.listed_on.isoformat() if item.listed_on else None,
                    "delisted_on": (
                        item.delisted_on.isoformat() if item.delisted_on else None
                    ),
                }
                for item in instruments_metadata
            ],
            "source_revisions": sorted({bar.source_revision for bar in bars}),
        },
        "quality": {
            "accepted": report.accepted,
            "coverage_ratio": _decimal_text(report.coverage_ratio),
            "issues": [asdict(issue) for issue in report.issues],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="验证免费日线覆盖与基础质量")
    parser.add_argument("--provider", choices=("baostock", "akshare"), required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--instrument",
        dest="instruments",
        action="append",
        required=True,
        help="规范证券代码，例如 600000.XSHG；可以重复提供",
    )
    parser.add_argument("--output", type=Path, help="只包含统计信息的 JSON 输出路径")
    args = parser.parse_args()
    try:
        result = run_probe(
            provider_name=args.provider,
            instruments=tuple(args.instruments),
            start=args.start,
            end=args.end,
        )
        exit_code = 0 if result["quality"]["accepted"] else 3  # type: ignore[index]
    except Exception as error:
        result = {
            "schema_version": "market-provider-probe-v0",
            "provider": args.provider,
            "request": {
                "instruments": tuple(args.instruments),
                "start": args.start.isoformat(),
                "end": args.end.isoformat(),
            },
            "status": "failed",
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        exit_code = 2
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return exit_code


def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


if __name__ == "__main__":
    raise SystemExit(main())
