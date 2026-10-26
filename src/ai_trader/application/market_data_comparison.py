from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from ai_trader.domain.market_data import DailyBar


@dataclass(frozen=True, slots=True)
class FieldComparison:
    field: str
    compared: int
    missing_values: int
    mismatches: int
    tolerance: Decimal
    maximum_absolute_difference: Decimal


@dataclass(frozen=True, slots=True)
class MarketDataComparison:
    left_rows: int
    right_rows: int
    overlapping_rows: int
    missing_from_left: int
    missing_from_right: int
    fields: tuple[FieldComparison, ...]


Tolerance = Callable[[DailyBar, DailyBar], Decimal]


def _fixed(value: str) -> Tolerance:
    return lambda _left, _right: Decimal(value)


_FIELDS: tuple[tuple[str, Callable[[DailyBar], Decimal | None], Tolerance], ...] = (
    ("open", lambda bar: bar.open, _fixed("0.001")),
    ("high", lambda bar: bar.high, _fixed("0.001")),
    ("low", lambda bar: bar.low, _fixed("0.001")),
    ("close", lambda bar: bar.close, _fixed("0.001")),
    (
        "volume_shares",
        lambda bar: bar.volume,
        lambda left, right: max(left.volume_resolution, right.volume_resolution),
    ),
    ("turnover_cny", lambda bar: bar.turnover, _fixed("1")),
)


def compare_daily_bars(
    left: tuple[DailyBar, ...], right: tuple[DailyBar, ...]
) -> MarketDataComparison:
    left_index = {(bar.instrument_id, bar.trading_date): bar for bar in left}
    right_index = {(bar.instrument_id, bar.trading_date): bar for bar in right}
    overlapping_keys = sorted(left_index.keys() & right_index.keys())
    comparisons = []
    for field, getter, tolerance_for in _FIELDS:
        compared = 0
        missing_values = 0
        mismatches = 0
        maximum = Decimal(0)
        maximum_tolerance = Decimal(0)
        for key in overlapping_keys:
            left_bar = left_index[key]
            right_bar = right_index[key]
            left_value = getter(left_bar)
            right_value = getter(right_bar)
            if left_value is None or right_value is None:
                missing_values += 1
                continue
            compared += 1
            difference = abs(left_value - right_value)
            maximum = max(maximum, difference)
            tolerance = tolerance_for(left_bar, right_bar)
            maximum_tolerance = max(maximum_tolerance, tolerance)
            if difference > tolerance:
                mismatches += 1
        comparisons.append(
            FieldComparison(
                field=field,
                compared=compared,
                missing_values=missing_values,
                mismatches=mismatches,
                tolerance=maximum_tolerance,
                maximum_absolute_difference=maximum,
            )
        )
    return MarketDataComparison(
        left_rows=len(left),
        right_rows=len(right),
        overlapping_rows=len(overlapping_keys),
        missing_from_left=len(right_index.keys() - left_index.keys()),
        missing_from_right=len(left_index.keys() - right_index.keys()),
        fields=tuple(comparisons),
    )

