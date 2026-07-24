from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_capital_manager import EnterpriseCapitalManager, InvestorCapitalInstruction
from src.dividend_bot.enterprise_portfolio import (
    EnterprisePortfolio,
    EnterprisePositionStatus,
    PortfolioEventType,
)
from src.dividend_bot.enterprise_strategy_execution import StrategyExecutionRequest
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now
from src.dividend_bot.strategy_framework import (
    StrategyConfiguration,
    StrategyDefinition,
    StrategyRegistry,
    StrategyStatus,
)


def _definition(strategy_id: str) -> StrategyDefinition:
    return StrategyDefinition(
        strategy_id=strategy_id,
        name=f"{strategy_id.title()} Strategy",
        version="1.0.0",
        supported_asset_types=("EQUITY",),
        required_intelligence=("FUNDAMENTALS",),
        supported_report_types=("WEEKLY",),
        supported_audit_types=("STRATEGY",),
        module_entry_point=f"src.dividend_bot.{strategy_id.lower()}_strategy_adapter",
    )


def _setup() -> tuple[StrategyRegistry, EnterpriseCapitalManager, EnterprisePortfolio]:
    registry = StrategyRegistry()
    for strategy_id in ("DIVIDEND", "SWING"):
        registry.register(_definition(strategy_id))
        registry.configure(StrategyConfiguration(strategy_id, "1.0.0", {}))
        registry.transition(strategy_id, StrategyStatus.CONFIGURED, "Configured")
        registry.transition(strategy_id, StrategyStatus.PAPER_VALIDATION, "Paper validation")
    capital = EnterpriseCapitalManager(registry)
    capital.record_deposit(20_000)
    capital.apply_investor_instruction(
        InvestorCapitalInstruction(
            "INVESTOR-1",
            {"DIVIDEND": 8_000, "SWING": 6_000},
            "Fund isolated strategies",
        )
    )
    return registry, capital, EnterprisePortfolio(registry, capital)


def _request(strategy_id: str = "DIVIDEND", amount: float = 2_000, action: str = "BUY") -> StrategyExecutionRequest:
    return StrategyExecutionRequest(
        request_id=uuid4(),
        decision_id=uuid4(),
        decision_public_id="DEC-2026-000001",
        strategy_id=strategy_id,
        effective_action=action,
        requested_capital=amount,
        available_strategy_capital=8_000 if strategy_id == "DIVIDEND" else 6_000,
        rationale="Governed paper request",
    )


def test_open_position_links_decision_request_and_strategy() -> None:
    _, _, portfolio = _setup()
    request = _request()
    position = portfolio.open_position(
        request,
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="Approved paper entry",
    )
    assert position.strategy_id == "DIVIDEND"
    assert position.decision_id == request.decision_id
    assert position.execution_request_id == request.request_id
    assert position.status is EnterprisePositionStatus.OPEN


def test_open_position_rejects_cost_over_request() -> None:
    _, _, portfolio = _setup()
    with pytest.raises(PlatformValidationError):
        portfolio.open_position(
            _request(amount=500),
            asset_symbol="SCHD",
            asset_type="ETF",
            quantity=10,
            entry_price=75,
            reason="Too expensive",
        )


def test_open_position_rejects_cost_over_remaining_strategy_capital() -> None:
    _, _, portfolio = _setup()
    portfolio.open_position(
        _request(amount=8_000),
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=100,
        entry_price=70,
        reason="First position",
    )
    with pytest.raises(PlatformValidationError):
        portfolio.open_position(
            _request(amount=2_000),
            asset_symbol="VYM",
            asset_type="ETF",
            quantity=20,
            entry_price=75,
            reason="Exceeds remaining capital",
        )


def test_non_entry_action_cannot_open_position() -> None:
    _, _, portfolio = _setup()
    with pytest.raises(PlatformValidationError):
        portfolio.open_position(
            _request(action="HOLD"),
            asset_symbol="SCHD",
            asset_type="ETF",
            quantity=10,
            entry_price=75,
            reason="Invalid open",
        )


def test_execution_request_can_create_only_one_position() -> None:
    _, _, portfolio = _setup()
    request = _request()
    portfolio.open_position(
        request,
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="First",
    )
    with pytest.raises(PlatformValidationError):
        portfolio.open_position(
            request,
            asset_symbol="VYM",
            asset_type="ETF",
            quantity=5,
            entry_price=100,
            reason="Duplicate request",
        )


def test_mark_position_updates_unrealized_profit_loss() -> None:
    _, _, portfolio = _setup()
    position = portfolio.open_position(
        _request(),
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="Open",
    )
    marked = portfolio.mark_position(
        position.position_id,
        strategy_id="DIVIDEND",
        current_price=80,
        reason="Daily paper mark",
    )
    assert marked.current_value == 800
    assert marked.unrealized_profit_loss == 50
    assert portfolio.events()[-1].event_type is PortfolioEventType.MARKED


def test_other_strategy_cannot_mark_position() -> None:
    _, _, portfolio = _setup()
    position = portfolio.open_position(
        _request(),
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="Open",
    )
    with pytest.raises(PlatformValidationError):
        portfolio.mark_position(
            position.position_id,
            strategy_id="SWING",
            current_price=80,
            reason="Cross strategy mark",
        )


def test_close_position_records_realized_profit_and_releases_logical_capacity() -> None:
    _, _, portfolio = _setup()
    position = portfolio.open_position(
        _request(),
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="Open",
    )
    assert portfolio.remaining_capital("DIVIDEND") == 7_250
    closed = portfolio.close_position(
        position.position_id,
        strategy_id="DIVIDEND",
        exit_price=82,
        reason="Governed paper exit",
    )
    assert closed.status is EnterprisePositionStatus.CLOSED
    assert closed.realized_profit_loss == 70
    assert portfolio.remaining_capital("DIVIDEND") == 8_000


def test_closed_position_cannot_be_closed_twice() -> None:
    _, _, portfolio = _setup()
    position = portfolio.open_position(
        _request(),
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="Open",
    )
    portfolio.close_position(
        position.position_id,
        strategy_id="DIVIDEND",
        exit_price=80,
        reason="Close",
    )
    with pytest.raises(PlatformValidationError):
        portfolio.close_position(
            position.position_id,
            strategy_id="DIVIDEND",
            exit_price=81,
            reason="Close again",
        )


def test_strategy_summaries_remain_isolated() -> None:
    _, _, portfolio = _setup()
    portfolio.open_position(
        _request("DIVIDEND", amount=2_000),
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="Dividend",
    )
    portfolio.open_position(
        _request("SWING", amount=2_000),
        asset_symbol="AMD",
        asset_type="EQUITY",
        quantity=10,
        entry_price=150,
        reason="Swing",
    )
    dividend = portfolio.strategy_summary("DIVIDEND")
    swing = portfolio.strategy_summary("SWING")
    assert dividend.open_cost_basis == 750
    assert swing.open_cost_basis == 1_500
    assert dividend.open_position_count == 1
    assert swing.open_position_count == 1


def test_positions_and_events_are_immutable_snapshots() -> None:
    _, _, portfolio = _setup()
    portfolio.open_position(
        _request(),
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="Open",
    )
    assert isinstance(portfolio.positions(), tuple)
    assert isinstance(portfolio.events(), tuple)


def test_suspended_strategy_cannot_open_new_position() -> None:
    registry, _, portfolio = _setup()
    registry.transition("DIVIDEND", StrategyStatus.SUSPENDED, "Suspend strategy")
    with pytest.raises(PlatformValidationError):
        portfolio.open_position(
            _request(),
            asset_symbol="SCHD",
            asset_type="ETF",
            quantity=10,
            entry_price=75,
            reason="Suspended",
        )


def test_snapshot_json_and_markdown_preserve_paper_boundary() -> None:
    _, _, portfolio = _setup()
    portfolio.open_position(
        _request(),
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="Open",
    )
    snapshot = portfolio.snapshot()
    json_output = portfolio.render_json(snapshot)
    markdown = portfolio.render_markdown(snapshot)
    assert '"broker_execution_enabled": false' in json_output
    assert "does not move cash, place orders, or call broker APIs" in markdown


def test_position_validation_rejects_unsafe_flags() -> None:
    _, _, portfolio = _setup()
    position = portfolio.open_position(
        _request(),
        asset_symbol="SCHD",
        asset_type="ETF",
        quantity=10,
        entry_price=75,
        reason="Open",
    )
    with pytest.raises(PlatformValidationError):
        replace(position, paper_trade_mode=False).validate()


def test_portfolio_has_no_broker_or_live_order_interface() -> None:
    _, _, portfolio = _setup()
    assert not hasattr(portfolio, "place_order")
    assert not hasattr(portfolio, "broker_request")
    assert not hasattr(portfolio, "execute_live_trade")
