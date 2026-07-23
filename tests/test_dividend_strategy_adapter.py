from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.dividend_bot.audit_framework import AuditCheckResult
from src.dividend_bot.dividend_strategy_adapter import (
    DIVIDEND_STRATEGY_DEFINITION,
    DividendStrategyAdapter,
    default_dividend_safety_checks,
)
from src.dividend_bot.platform_entities import (
    FindingStatus,
    MasterCompanyIntelligenceProfile,
    new_identity,
)
from src.dividend_bot.platform_foundation import IdentifierKind, PlatformValidationError
from src.dividend_bot.strategy_framework import StrategyRegistry

NOW = datetime(2026, 7, 29, tzinfo=timezone.utc)


def profile(income=80.0, risk=20.0, quality=90.0):
    return MasterCompanyIntelligenceProfile(
        identity=new_identity(IdentifierKind.PROFILE),
        company_id=uuid4(),
        income={"score": income},
        risk={"score": risk},
        quality_score=quality,
    )


def test_dividend_definition_is_paper_only():
    DIVIDEND_STRATEGY_DEFINITION.validate()
    assert DIVIDEND_STRATEGY_DEFINITION.paper_trade_mode is True
    assert DIVIDEND_STRATEGY_DEFINITION.live_trading_enabled is False
    assert DIVIDEND_STRATEGY_DEFINITION.broker_execution_enabled is False


def test_adapter_registers_and_configures_dividend():
    registry = StrategyRegistry()
    DividendStrategyAdapter.register(registry)
    assert registry.get("DIVIDEND").name == "Dividend Strategy"
    assert registry.get_configuration("DIVIDEND").parameters["paper_trade_mode"] is True


def test_strong_profile_creates_paper_buy_review():
    result = DividendStrategyAdapter().evaluate(profile())
    assert result.evaluation.strategy_id == "DIVIDEND"
    assert result.recommendation.paper_action == "REVIEW_FOR_PAPER_BUY"


def test_weak_profile_creates_watchlist_recommendation():
    result = DividendStrategyAdapter().evaluate(profile(income=20.0, risk=80.0, quality=30.0))
    assert result.recommendation.paper_action == "WATCHLIST"


def test_evaluation_does_not_mutate_mcip():
    source = profile()
    before = dict(source.income)
    DividendStrategyAdapter().evaluate(source)
    assert dict(source.income) == before


def test_invalid_shared_score_is_rejected():
    with pytest.raises(PlatformValidationError):
        DividendStrategyAdapter().evaluate(profile(income="high"))


def test_weekly_report_is_dividend_scoped():
    model = DividendStrategyAdapter().build_report(
        report_type="weekly",
        period_start=NOW,
        period_end=NOW,
        metrics={"total_return_pct": 3.5, "income": 12.0},
    )
    assert model.strategy_id == "DIVIDEND"
    assert model.report_type == "WEEKLY"
    assert model.title == "Dividend Weekly Report"


def test_unsupported_report_type_is_rejected():
    with pytest.raises(PlatformValidationError):
        DividendStrategyAdapter().build_report(
            report_type="SWING_JOURNAL",
            period_start=NOW,
            period_end=NOW,
            metrics={},
        )


def test_dividend_audit_is_isolated():
    model = DividendStrategyAdapter().build_audit(
        audit_type="WEEKLY_AUDIT",
        completed_at=NOW,
        checks=(AuditCheckResult("paper_only", FindingStatus.PASS, "verified"),),
    )
    assert model.strategy_id == "DIVIDEND"
    assert model.scope_type == "STRATEGY"


def test_default_safety_checks_cover_permanent_rules():
    checks = default_dividend_safety_checks()
    assert len(checks) == 3
    assert all(check.status is FindingStatus.PASS for check in checks)
