from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from src.dividend_bot.dividend_enterprise_execution import (
    DividendEnterpriseExecutionService,
    DividendPaperDisposition,
)
from src.dividend_bot.dividend_strategy_adapter import DividendStrategyAdapter
from src.dividend_bot.enterprise_capital_manager import EnterpriseCapitalManager, InvestorCapitalInstruction
from src.dividend_bot.enterprise_strategy_execution import (
    EnterpriseStrategyExecutionCoordinator,
    StrategyExecutionRequest,
    StrategyResponseStatus,
)
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now
from src.dividend_bot.strategy_framework import StrategyRegistry, StrategyStatus


def _profile(*, suitable: bool = True) -> MasterCompanyIntelligenceProfile:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCIP"),
        company_id=uuid4(),
        income={"score": 80 if suitable else 20},
        risk={"score": 20 if suitable else 90},
        fundamentals={"score": 80},
        financial_health={"score": 80},
        earnings={"days": 30},
        quality_score=85 if suitable else 30,
    )
    profile.validate()
    return profile


def _setup(*, action: str = "BUY"):
    registry = StrategyRegistry()
    DividendStrategyAdapter.register(registry)
    registry.transition("DIVIDEND", StrategyStatus.CONFIGURED, "Configured")
    registry.transition("DIVIDEND", StrategyStatus.PAPER_VALIDATION, "Paper validation")
    capital = EnterpriseCapitalManager(registry)
    capital.record_deposit(10_000)
    capital.apply_investor_instruction(
        InvestorCapitalInstruction("INVESTOR-1", {"DIVIDEND": 5_000}, "Fund Dividend")
    )
    coordinator = EnterpriseStrategyExecutionCoordinator(registry, capital)
    request = StrategyExecutionRequest(
        request_id=uuid4(),
        decision_id=uuid4(),
        decision_public_id="DEC-2026-000001",
        strategy_id="DIVIDEND",
        effective_action=action,
        requested_capital=1_000,
        available_strategy_capital=5_000,
        rationale="Governed Dividend paper request",
    )
    request.validate()
    coordinator._requests.append(request)
    return coordinator, request, DividendEnterpriseExecutionService(coordinator)


def test_suitable_buy_is_accepted_for_paper_review() -> None:
    _, request, service = _setup(action="BUY")
    record = service.process(request, _profile(suitable=True))
    assert record.disposition is DividendPaperDisposition.PAPER_BUY_REVIEW
    assert record.response.status is StrategyResponseStatus.ACCEPTED


def test_unsuitable_buy_is_deferred() -> None:
    _, request, service = _setup(action="BUY")
    record = service.process(request, _profile(suitable=False))
    assert record.disposition is DividendPaperDisposition.DEFERRED
    assert record.response.status is StrategyResponseStatus.DEFERRED


def test_exit_request_is_accepted_for_exit_review() -> None:
    _, request, service = _setup(action="EXIT")
    record = service.process(request, _profile())
    assert record.disposition is DividendPaperDisposition.EXIT_REVIEW
    assert record.response.status is StrategyResponseStatus.ACCEPTED


def test_hold_request_is_non_transactional_monitoring() -> None:
    _, request, service = _setup(action="HOLD")
    record = service.process(request, _profile())
    assert record.disposition is DividendPaperDisposition.HOLD_REVIEW


def test_watchlist_result_is_preserved() -> None:
    _, request, service = _setup(action="WATCH")
    record = service.process(request, _profile(suitable=False))
    assert record.disposition is DividendPaperDisposition.WATCHLIST


def test_other_strategy_request_is_rejected() -> None:
    coordinator, request, service = _setup()
    invalid = replace(request, strategy_id="SWING")
    with pytest.raises(PlatformValidationError):
        service.process(invalid, _profile())


def test_duplicate_processing_is_rejected() -> None:
    _, request, service = _setup()
    service.process(request, _profile())
    with pytest.raises(PlatformValidationError):
        service.process(request, _profile())


def test_unsupported_action_is_rejected() -> None:
    _, request, service = _setup()
    invalid = replace(request, effective_action="UNKNOWN")
    with pytest.raises(PlatformValidationError):
        service.process(invalid, _profile())


def test_records_are_append_only_snapshots() -> None:
    _, request, service = _setup()
    service.process(request, _profile())
    assert isinstance(service.records(), tuple)
    assert len(service.records()) == 1


def test_response_is_recorded_in_enterprise_coordinator() -> None:
    coordinator, request, service = _setup()
    record = service.process(request, _profile())
    snapshot = coordinator.snapshot(request.request_id)
    assert snapshot.response == record.response


def test_json_and_markdown_preserve_dividend_scope_and_boundary() -> None:
    _, request, service = _setup()
    record = service.process(request, _profile())
    json_output = service.render_json(record)
    markdown = service.render_markdown(record)
    assert '"strategy_id": "DIVIDEND"' in json_output
    assert '"broker_execution_enabled": false' in json_output
    assert "Dividend Enterprise Paper Execution" in markdown
    assert "does not reserve capital, place orders, or call broker APIs" in markdown


def test_record_rejects_unsafe_flags() -> None:
    _, request, service = _setup()
    record = service.process(request, _profile())
    with pytest.raises(PlatformValidationError):
        replace(record, paper_trade_mode=False).validate()


def test_processed_at_must_be_timezone_aware() -> None:
    _, request, service = _setup()
    record = service.process(request, _profile())
    with pytest.raises(PlatformValidationError):
        replace(record, processed_at=record.processed_at.replace(tzinfo=None)).validate()


def test_service_has_no_broker_or_order_interface() -> None:
    _, _, service = _setup()
    assert not hasattr(service, "place_order")
    assert not hasattr(service, "broker_request")
    assert not hasattr(service, "execute_live_trade")
