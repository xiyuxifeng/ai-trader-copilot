import argparse
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from ai_trader.application.market_data_comparison import compare_daily_bars
from ai_trader.infrastructure.market_data.akshare_provider import AKShareMarketDataProvider
from ai_trader.infrastructure.market_data.baostock_provider import BaoStockMarketDataProvider


def run_comparison(
    *, instruments: tuple[str, ...], start: date, end: date
) -> dict[str, object]:
    baostock = BaoStockMarketDataProvider()
    akshare = AKShareMarketDataProvider()
    left = tuple(
        bar
        for instrument_id in instruments
        for bar in baostock.fetch_daily_bars(
            instrument_id=instrument_id, start=start, end=end
        )
    )
    right = tuple(
        bar
        for instrument_id in instruments
        for bar in akshare.fetch_daily_bars(instrument_id=instrument_id, start=start, end=end)
    )
    comparison = compare_daily_bars(left, right)
    return {
        "schema_version": "market-provider-comparison-v0",
        "left_provider": "baostock",
        "right_provider": "akshare",
        "request": {
            "instruments": instruments,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "comparison": _json_safe(asdict(comparison)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="对账 BaoStock 与 AKShare 未复权日线")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--instrument", dest="instruments", action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = run_comparison(
            instruments=tuple(args.instruments), start=args.start, end=args.end
        )
        exit_code = 0
    except Exception as error:
        result = {
            "schema_version": "market-provider-comparison-v0",
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


def _json_safe(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())

