from dataclasses import dataclass
from datetime import date

from ai_trader.domain.profile import UserProfile


@dataclass(frozen=True, slots=True)
class TodayView:
    setup_required: bool
    market_summary: str
    data_as_of: date | None
    positions_message: str
    candidates_message: str
    exceptions_count: int
    learning_message: str


def build_today_view(profile: UserProfile | None) -> TodayView:
    if profile is None:
        return TodayView(
            setup_required=True,
            market_summary="完成首次设置后，交易员才能按你的风险边界工作。",
            data_as_of=None,
            positions_message="尚未设置持仓分析。",
            candidates_message="尚未开始扫描候选股票。",
            exceptions_count=0,
            learning_message="后台研究尚未开始。",
        )

    return TodayView(
        setup_required=False,
        market_summary="行情数据尚未接入，今天不生成操作建议。",
        data_as_of=None,
        positions_message="当前没有需要处理的持仓。",
        candidates_message="当前没有可验证的候选机会。",
        exceptions_count=0,
        learning_message="系统骨架运行正常，文章学习将在下一阶段接入。",
    )

