from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from src.dividend_bot.dividend_enterprise_execution import (
    DividendPaperDisposition,
    DividendPaperExecutionRecord,
)
from src.dividend_bot.dividend_portfolio_integration import (
    DividendPortfolioAction,
    DividendPortfolioIntegrationService,
)
from src.dividend_bot.dividend_strategy_adapter import DividendStrategyAdapter
from src.dividend_bot.enterprise_capital_manager import EnterpriseCapitalManager, InvestorCapitalInstruction
from src.dividend_bot.enterprise_portfolio import EnterprisePortfolio, EnterprisePositionStatus
from src.dividend_bot.enterprise_strategy_execution import (
    StrategyExecutionRequest,
    StrategyExecutionResponse,
    StrategyResponseStatus,
)
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now
from src.dividend_bot.strategy_framework import StrategyRegistry, StrategyStatus


def _setup():
    registry = StrategyRegistry()
    DividendStrategyAdapter.register(registry)
    registry.transition("DIVIDEND", StrategyStatus.CONFIGURED, "Configured")
    registry.transition("DIVIDEND", StrategyStatus.PAPER_VALIDATION, "Paper validation")
    capital = EnterpriseCapitalManager(registry)
    capital.record_deposit(10_000)
    capital.apply_investor_instruction(
        InvestorCapitalInstruction("INVESTOR-1", {"DIVIDEND": 5_000}, "Fund Dividend")
    )
    portfolio = EnterprisePortfolio(registry, capital)
    return portfolio, DividendPortfolioIntegrationService(portfolio)


def _profile(*, suitable: bool = True) -> MasterCompanyIntelligenceProfile:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCI"),
        company_id=uuid4(),
        income={"score": 80.0 if suitable else 20.0},
        risk={"score": 20.0 if suitable else 90.0},
        quality_score=80.0 if suitable else 20.0,
    )
    profile.validate()
    return profile


def _execution(
    *,
    action: str = "BUY",
    disposition: DividendPaperDisposition = DividendPaperDisposition.PAPER_BUY_REVIEW,
    response_status: StrategyResponseStatus = StrategyResponseStatus.ACCEPTED,
) -> DividendPaperExecutionRecord:
    request = StrategyExecutionRequest(
        request_id=uuid4(),
        decision_id=uuid4(),
        decision_public_id="DEC-2026-000001",
        strategy_id="DIVIDEND",
        effective_action=action,
        requested_capital=1_000,
        available_strategy_capital=5_000,
        rationale="Governed paper request",
    )
    evaluation = DividendStrategyAdapter().evaluate(_profile())
    response = StrategyExecutionResponse(
        response_id=uuid4(),
        request_id=request.request_id,
        strategy_id="DIVIDEND",
        status=response_status,
        explanation="Strategy response",
    )
    record = DividendPaperExecutionRecord(
        record_id=uuid4(),
        request=request,
        evaluation_result=evaluation,
        response=response,
        disposition=disposition,
    )
    record.validate()
    return record


def test_buy_execution_opens_enterprise_position() -> None:
    portfolio, service = _setup()
    result = service.apply(
        _execution(), asset_symbol="SCHD", quantity=10, price=50, explanation="Paper open"
    )
    assert result.action is DividendPortfolioAction.OPENED
    assert result.position is not None
    assert result.position.asset_symbol == "SCHD"
    assert portfolio.strategy_summary("DIVIDEND").open_position_count == 1


def test_open_position_preserves_decision_and_request_links() -> None:
    _, service = _setup()
    execution = _execution()
    result = service.apply(execution, asset_symbol="SCHD", quantity=5, price=100, explanation="Open")
    assert result.position.decision_id == execution.request.decision_id
    assert result.position.execution_request_id == execution.request.request_id


def test_buy_requires_quantity_and_price() -> None:
    _, service = _setup()
    with pytest.raises(PlatformValidationError):
        service.apply(_execution(), asset_symbol="SCHD", explanation="Missing values")


def test_deferred_execution_is_rejected() -> None:
    _, service = _setup()
    with pytest.raises(PlatformValidationError):
        service.apply(
            _execution(response_status=StrategyResponseStatus.DEFERRED),
            asset_symbol="SCHD",
            quantity=1,
            price=50,
            explanation="Deferred",
        )


def test_hold_review_creates_no_position_change() -> None:
    portfolio, service = _setup()
    result = service.apply(
        _execution(action="HOLD", disposition=DividendPaperDisposition.HOLD_REVIEW),
        asset_symbol="SCHD",
        explanation="Continue monitoring",
    )
    assert result.action is DividendPortfolioAction.NO_POSITION_CHANGE
    assert result.position is None
    assert portfolio.positions("DIVIDEND") == ()


def test_watchlist_creates_no_position_change() -> None:
    _, service = _setup()
    result = service.apply(
        _execution(action="WATCH", disposition=DividendPaperDisposition.WATCHLIST),
        asset_symbol="SCHD",
        explanation="Watch only",
    )
    assert result.action is DividendPortfolioAction.NO_POSITION_CHANGE


def test_exit_review_closes_existing_position() -> None:
    portfolio, service = _setup()
    opened = service.apply(_execution(), asset_symbol="SCHD", quantity=10, price=50, explanation="Open")
    exit_execution = _execution(action="SELL", disposition=DividendPaperDisposition.EXIT_REVIEW)
    closed = service.apply(
        exit_execution,
        asset_symbol="SCHD",
        position_id=opened.position.position_id,
        price=60,
        explanation="Paper exit",
    )
    assert closed.action is DividendPortfolioAction.CLOSED
    assert closed.position.status is EnterprisePositionStatus.CLOSED
    assert closed.position.realized_profit_loss == 100


def test_exit_requires_position_id_and_price() -> None:
    _, service = _setup()
    with pytest.raises(PlatformValidationError):
        service.apply(
            _execution(action="EXIT", disposition=DividendPaperDisposition.EXIT_REVIEW),
            asset_symbol="SCHD",
            explanation="Exit",
        )


def test_duplicate_execution_processing_is_rejected() -> None:
    _, service = _setup()
    execution = _execution()
    service.apply(execution, asset_symbol="SCHD", quantity=1, price=50, explanation="Open")
    with pytest.raises(PlatformValidationError):
        service.apply(execution, asset_symbol="SCHD", quantity=1, price=50, explanation="Again")


def test_cross_strategy_execution_is_rejected() -> None:
    _, service = _setup()
    execution = _execution()
    unsafe_request = replace(execution.request, strategy_id="SWING")
    unsafe_response = replace(execution.response, strategy_id="SWING")
    unsafe = replace(execution, request=unsafe_request, response=unsafe_response)
    with pytest.raises(PlatformValidationError):
        service.apply(unsafe, asset_symbol="SCHD", quantity=1, price=50, explanation="Wrong strategy")


def test_records_are_append_only_tuple_snapshots() -> None:
    _, service = _setup()
    service.apply(_execution(), asset_symbol="SCHD", quantity=1, price=50, explanation="Open")
    assert isinstance(service.records(), tuple)
    assert len(service.records()) == 1


def test_json_and_markdown_preserve_paper_boundary() -> None:
    _, service = _setup()
    record = service.apply(_execution(), asset_symbol="SCHD", quantity=1, price=50, explanation="Open")
    json_output = service.render_json(record)
    markdown = service.render_markdown(record)
    assert '"broker_execution_enabled": false' in json_output
    assert "does not move cash, place orders, or call broker APIs" in markdown


def test_integration_record_rejects_unsafe_flags() -> None:
    _, service = _setup()
    record = service.apply(_execution(), asset_symbol="SCHD", quantity=1, price=50, explanation="Open")
    with pytest.raises(PlatformValidationError):
        replace(record, paper_trade_mode=False).validate()


def test_integration_timestamp_is_timezone_aware() -> None:
    _, service = _setup()
    record = service.apply(
        _execution(), asset_symbol="SCHD", quantity=1, price=50, explanation="Open", integrated_at=utc_now()
    )
    assert record.integrated_at.tzinfo is not None


def test_service_has_no_broker_or_order_interface() -> None:
    _, service = _setup()
    assert not hasattr(service, "place_order")
    assert not hasattr(service, "broker_request")
    assert not hasattr(service, "execute_live_trade")
