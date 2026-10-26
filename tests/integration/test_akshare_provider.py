from datetime import date

import pandas as pd

from ai_trader.application.market_data_quality import validate_daily_bars
from ai_trader.domain.market_data import TradeStatus, VolumeUnit
from ai_trader.infrastructure.market_data.akshare_provider import AKShareMarketDataProvider


class FakeAKShare:
    def stock_zh_a_hist(self, **kwargs) -> pd.DataFrame:
        assert kwargs["symbol"] == "600000"
        assert kwargs["adjust"] == ""
        assert kwargs["timeout"] == 9
        return pd.DataFrame(
            [
                {
                    "日期": date(2024, 1, 2),
                    "股票代码": "600000",
                    "开盘": 9.1,
                    "收盘": 9.2,
                    "最高": 9.3,
                    "最低": 9.0,
                    "成交量": 10,
                    "成交额": 9200,
                }
            ]
        )

    def tool_trade_date_hist_sina(self) -> pd.DataFrame:
        return pd.DataFrame({"trade_date": [date(2024, 1, 2), date(2024, 1, 3)]})


def test_maps_akshare_lots_to_shares_but_blocks_missing_factors() -> None:
    provider = AKShareMarketDataProvider(client=FakeAKShare(), timeout_seconds=9)
    start = end = date(2024, 1, 2)

    bars = provider.fetch_daily_bars(instrument_id="600000.XSHG", start=start, end=end)
    calendar = provider.fetch_trade_calendar(start=start, end=end)
    factors = provider.fetch_adjustment_factors(
        instrument_id="600000.XSHG", start=start, end=end
    )
    report = validate_daily_bars(bars, calendar, factors)

    assert bars[0].volume == 1000
    assert bars[0].volume_unit is VolumeUnit.SHARES
    assert bars[0].volume_resolution == 100
    assert bars[0].trade_status is TradeStatus.NORMAL
    assert factors == ()
    assert report.accepted is False
    assert [issue.code for issue in report.issues] == ["missing_adjustment_factor"]
