"""Tests for strategy_learning_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import strategy_learning_engine as engine


def _observations(strategy: str, count: int, total_return: float, win: bool = True, drawdown: float = 10.0, self_funding: float = 80.0):
    return [
        {
            "strategy_name": strategy,
            "completed": True,
            "total_return_pct": total_return,
            "income_growth_pct": 8.0,
            "monthly_income": 5.0,
            "max_drawdown_pct": drawdown,
            "recovery_days": 20,
            "volatility_score": 45,
            "win": win,
            "tax_efficiency_score": 70,
            "capital_efficiency_score": 80,
            "self_funding_score": self_funding,
        }
        for _ in range(count)
    ]


def test_dataclasses_exist():
    assert hasattr(engine, "StrategyObservation")
    assert hasattr(engine, "LearningProposal")
    assert hasattr(engine, "StrategyLearningReport")


def test_public_functions_exist():
    for name in [
        "summarize_strategies",
        "evidence_is_sufficient",
        "generate_learning_proposals",
        "approve_learning_proposal",
        "build_strategy_learning_report",
        "validate_strategy_learning_report",
        "write_strategy_learning_report_json",
        "read_strategy_learning_report_json",
        "write_strategy_learning_report_csv",
        "format_strategy_learning_report_markdown",
        "write_strategy_learning_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_is_observation_only():
    payload = engine.build_strategy_learning_report()
    assert engine.validate_strategy_learning_report(payload) is True
    assert payload["learning_mode"] == "SEMI_ADAPTIVE"
    assert payload["approval_required"] is True
    assert payload["learning_status"] == "OBSERVATION_ONLY"
    assert payload["learning_proposals"] == []


def test_minimum_evidence_constants():
    assert engine.MIN_COMPLETED_OPPORTUNITIES == 30
    assert engine.MIN_HISTORY_MONTHS == 6
    assert engine.MIN_OBSERVATIONS_PER_STRATEGY == 10


def test_strategy_summaries_rank_best_first():
    rows = _observations("STRATEGY_A", 10, 30.0) + _observations("STRATEGY_B", 10, 10.0)
    summaries = engine.summarize_strategies(rows)
    assert summaries[0]["strategy_name"] == "STRATEGY_A"
    assert summaries[0]["learning_score"] > summaries[1]["learning_score"]


def test_evidence_is_insufficient_before_thresholds():
    summaries = engine.summarize_strategies(_observations("STRATEGY_A", 10, 20.0))
    assert engine.evidence_is_sufficient(29, 6, summaries) is False
    assert engine.evidence_is_sufficient(30, 5, summaries) is False


def test_evidence_is_sufficient_at_thresholds():
    rows = _observations("STRATEGY_A", 15, 25.0) + _observations("STRATEGY_B", 15, 15.0)
    summaries = engine.summarize_strategies(rows)
    assert engine.evidence_is_sufficient(30, 6, summaries) is True


def test_report_generates_advisory_proposals_with_sufficient_evidence():
    rows = _observations("ETF_PAIR", 15, 35.0, self_funding=90.0) + _observations("COVERED_CALL", 15, 8.0, self_funding=50.0)
    payload = engine.build_strategy_learning_report(rows, history_months=6)
    assert payload["learning_status"] == "ELIGIBLE_FOR_REVIEW"
    assert payload["proposal_count"] >= 1
    assert all(p["requires_approval"] is True for p in payload["learning_proposals"])
    assert all(p["status"] == "WAITING_FOR_APPROVAL" for p in payload["learning_proposals"])


def test_proposals_do_not_modify_production_rules():
    rows = _observations("ETF_PAIR", 15, 35.0) + _observations("COVERED_CALL", 15, 8.0)
    before = dict(engine.__dict__.get("MASTER_SCORE_WEIGHTS", {}))
    engine.build_strategy_learning_report(rows, history_months=6)
    after = dict(engine.__dict__.get("MASTER_SCORE_WEIGHTS", {}))
    assert before == after


def test_approve_learning_proposal_requires_user_identity():
    proposal = engine.generate_learning_proposals(
        engine.summarize_strategies(_observations("A", 10, 30.0) + _observations("B", 10, 5.0))
    )[0]
    with pytest.raises(ValueError):
        engine.approve_learning_proposal(proposal, "")


def test_approve_learning_proposal_sets_approval_fields():
    proposal = engine.generate_learning_proposals(
        engine.summarize_strategies(_observations("A", 10, 30.0) + _observations("B", 10, 5.0))
    )[0]
    approved = engine.approve_learning_proposal(proposal, "Percy", "2026-07-10T12:00:00Z")
    assert approved["status"] == "APPROVED"
    assert approved["approved_by"] == "Percy"
    assert approved["approved_at_utc"] == "2026-07-10T12:00:00Z"


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_strategy_learning_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_strategy_learning_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_strategy_learning_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_strategy_learning_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
        ("approval_required", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_strategy_learning_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_strategy_learning_report_json()
    assert engine.read_strategy_learning_report_json() == payload
    engine.write_strategy_learning_report_csv()
    engine.write_strategy_learning_report_markdown()
    assert Path("strategy_learning_report.json").exists()
    assert Path("strategy_learning_report.csv").exists()
    assert Path("strategy_learning_report.md").exists()
    markdown = engine.format_strategy_learning_report_markdown(payload)
    assert "# Strategy Learning Report" in markdown
    assert "## Strategy Summaries" in markdown
    assert "## Learning Proposals" in markdown
    assert "## Safety Guarantees" in markdown


def test_static_safety_no_restricted_execution_terms():
    source = Path(engine.__file__).read_text(encoding="utf-8").lower()
    restricted = [
        "import " + "robinhood",
        "from " + "robinhood",
        "place" + "_order(",
        "submit" + "_order(",
        "execute" + "_order(",
    ]
    for item in restricted:
        assert item not in source


def test_static_safety_no_process_or_network_terms():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    restricted = [
        "import sub" + "process",
        "sub" + "process.",
        "os." + "system(",
        "requests.",
        "urllib." + "request",
        "socket.",
    ]
    for item in restricted:
        assert item not in source
