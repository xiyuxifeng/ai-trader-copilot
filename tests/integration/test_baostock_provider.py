from datetime import date
from types import SimpleNamespace

from ai_trader.domain.market_data import AvailabilityBasis, TradeStatus, VolumeUnit
from ai_trader.infrastructure.market_data.baostock_provider import BaoStockMarketDataProvider


class FakeResult:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.error_code = "0"
        self.error_msg = "success"
        self.fields = list(rows[0]) if rows else []
        self._rows = rows
        self._index = -1

    def next(self) -> bool:
        self._index += 1
        return self._index < len(self._rows)

    def get_row_data(self) -> list[str]:
        row = self._rows[self._index]
        return [row[field] for field in self.fields]


class FakeBaoStock:
    def __init__(self) -> None:
        self.logged_out = False

    def login(self) -> SimpleNamespace:
        return SimpleNamespace(error_code="0", error_msg="success")

    def logout(self) -> None:
        self.logged_out = True

    def query_history_k_data_plus(self, *args, **kwargs) -> FakeResult:
        assert args[0] == "sh.600000"
        assert kwargs["adjustflag"] == "3"
        return FakeResult(
            [
                {
                    "date": "2024-01-02",
                    "code": "sh.600000",
                    "open": "9.10",
                    "high": "9.30",
                    "low": "9.00",
                    "close": "9.20",
                    "preclose": "9.05",
                    "volume": "1000",
                    "amount": "9200",
                    "adjustflag": "3",
                    "tradestatus": "1",
                    "isST": "0",
                }
            ]
        )

    def query_trade_dates(self, **kwargs) -> FakeResult:
        return FakeResult([{"calendar_date": "2024-01-02", "is_trading_day": "1"}])

    def query_adjust_factor(self, *args, **kwargs) -> FakeResult:
        assert kwargs["start_date"] == "1990-01-01"
        return FakeResult(
            [
                {
                    "code": "sh.600000",
                    "dividOperateDate": "2024-01-02",
                    "foreAdjustFactor": "1.2",
                    "backAdjustFactor": "0.8",
                    "adjustFactor": "1.0",
                }
            ]
        )


def test_maps_unadjusted_bars_calendar_and_factors() -> None:
    client = FakeBaoStock()
    provider = BaoStockMarketDataProvider(client=client)
    start = end = date(2024, 1, 2)

    bars = provider.fetch_daily_bars(instrument_id="600000.XSHG", start=start, end=end)
    calendar = provider.fetch_trade_calendar(start=start, end=end)
    factors = provider.fetch_adjustment_factors(
        instrument_id="600000.XSHG", start=start, end=end
    )

    assert bars[0].instrument_id == "600000.XSHG"
    assert bars[0].trade_status is TradeStatus.NORMAL
    assert bars[0].availability_basis is AvailabilityBasis.CONSERVATIVE_POLICY
    assert bars[0].volume_unit is VolumeUnit.SHARES
    assert bars[0].volume_resolution == 1
    assert calendar[0].is_trading_day is True
    assert str(factors[0].raw_factor) == "1.0"
    assert client.logged_out is True

