from decimal import Decimal
from uuid import uuid4

import pytest

from ai_trader.domain.profile import RiskLevel, build_risk_policy, recommended_position_limit


@pytest.mark.parametrize(
    ("risk_level", "expected"),
    [
        (RiskLevel.CONSERVATIVE, Decimal("0.10")),
        (RiskLevel.BALANCED, Decimal("0.20")),
        (RiskLevel.AGGRESSIVE, Decimal("0.30")),
    ],
)
def test_recommended_position_limit(risk_level: RiskLevel, expected: Decimal) -> None:
    assert recommended_position_limit(risk_level) == expected


def test_policy_keeps_live_trading_disabled() -> None:
    policy = build_risk_policy(
        profile_id=uuid4(),
        risk_level=RiskLevel.BALANCED,
        requested_limit=Decimal("0.18"),
        version=1,
    )

    assert policy.max_single_position == Decimal("0.18")
    assert policy.live_trading_enabled is False
    assert policy.new_rule_confirmation_required is True


@pytest.mark.parametrize("limit", [Decimal("0.04"), Decimal("0.51"), Decimal("0.123")])
def test_policy_rejects_unsafe_or_over_precise_limits(limit: Decimal) -> None:
    with pytest.raises(ValueError):
        build_risk_policy(
            profile_id=uuid4(),
            risk_level=RiskLevel.BALANCED,
            requested_limit=limit,
            version=1,
        )

