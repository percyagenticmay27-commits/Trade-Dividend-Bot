"""Tests for stage_input_adapters.py."""
from __future__ import annotations

import stage_input_adapters as adapters


def test_build_portfolio_decision_candidates_merges_upstream_scores():
    payloads = {
        "opportunity_pairing": {"opportunities": [{"income_symbol": "AAA", "combined_score": 88, "self_funding_score": 75}]},
        "dividend_ranking": {"rankings": [{"symbol": "AAA", "overall_score": 82}]},
        "conviction": {"conviction_score": 79, "confidence": 0.8, "confidence_level": "HIGH"},
        "entry_score": {"entry_score": 77},
        "momentum_score": {"momentum_score": 74},
    }
    rows = adapters.build_portfolio_decision_candidates(payloads)
    assert rows[0]["symbol"] == "AAA"
    assert rows[0]["opportunity_score"] == 88
    assert rows[0]["dividend_ranking_score"] == 82
    assert rows[0]["conviction_score"] == 79
    assert rows[0]["entry_score"] == 77
    assert rows[0]["momentum_score"] == 74


def test_build_lifecycle_holdings_prefers_construction():
    payloads = {
        "portfolio_construction": {"positions": [{"symbol": "AAA"}]},
        "capital_allocation": {"allocations": [{"symbol": "BBB"}]},
    }
    assert adapters.build_lifecycle_holdings(payloads) == [{"symbol": "AAA"}]


def test_prepare_stage_kwargs_filters_to_builder_signature():
    def builder(decisions=None, root_path="."):
        return decisions, root_path

    payloads = {"opportunity_pairing": {"opportunities": [{"symbol": "AAA", "combined_score": 90}]}}
    kwargs = adapters.prepare_stage_kwargs("portfolio_decision", payloads, builder, "/tmp/x")
    assert set(kwargs) == {"decisions", "root_path"}
    assert kwargs["decisions"][0]["symbol"] == "AAA"


def test_daily_command_center_receives_upstream_payloads():
    def builder(portfolio_lifecycle=None, portfolio_decision=None):
        return {}

    payloads = {
        "portfolio_lifecycle": {"portfolio_value": 500},
        "portfolio_decision": {"portfolio_decisions": [{"symbol": "AAA"}]},
    }
    kwargs = adapters.prepare_stage_kwargs("daily_command_center", payloads, builder)
    assert kwargs["portfolio_lifecycle"]["portfolio_value"] == 500
    assert kwargs["portfolio_decision"]["portfolio_decisions"][0]["symbol"] == "AAA"
