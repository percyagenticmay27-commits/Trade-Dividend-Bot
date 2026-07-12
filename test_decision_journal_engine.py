import json
from pathlib import Path

import pytest

import decision_journal_engine as engine


def sample_decision():
    return {
        "autonomy_level": "LEVEL_1_ADVISOR",
        "final_capital_action": "KEEP",
        "decision_reason": "CURRENT_ALLOCATION_REMAINS_PREFERRED",
        "ai_cio_verdict": "Recommendation: Continue holding AMDW + PLTU.",
        "current_candidate_id": "AMDW + PLTU",
        "challenger_candidate_id": "AMDW + GGLL",
        "capital_efficiency_score_difference": 2.0,
        "decision_stability_score": 82.7,
        "decision_stability_label": "STABLE",
        "evidence_confidence_score": 94.0,
        "evidence_confidence_label": "VERY_HIGH",
        "market_regime": "BULL",
        "investment_policy_compliant": True,
        "policy_action_allowed": True,
        "automatic_paper_action_authorized": False,
        "investor_override_available": True,
        "warnings": [],
    }


def test_public_functions_exist():
    assert callable(engine.build_decision_journal_entry)
    assert callable(engine.append_decision_journal_entry)
    assert callable(engine.format_decision_journal_markdown)
    assert callable(engine.write_decision_journal)


def test_build_entry_preserves_decision_and_portfolios():
    entry = engine.build_decision_journal_entry(
        ai_cio_decision=sample_decision(),
        portfolio_before={"AMDW + PLTU": 100.0},
        portfolio_after={"AMDW + PLTU": 100.0},
    )
    assert entry["final_capital_action"] == "KEEP"
    assert entry["portfolio_before"] == {"AMDW + PLTU": 100.0}
    assert entry["portfolio_after"] == {"AMDW + PLTU": 100.0}
    assert entry["entry_id"]


def test_invalid_decision_rejected():
    with pytest.raises(ValueError):
        engine.build_decision_journal_entry(ai_cio_decision=[], portfolio_before={})


def test_invalid_portfolio_rejected():
    with pytest.raises(ValueError):
        engine.build_decision_journal_entry(ai_cio_decision=sample_decision(), portfolio_before=[])


def test_invalid_investor_response_rejected():
    with pytest.raises(ValueError):
        engine.build_decision_journal_entry(
            ai_cio_decision=sample_decision(),
            portfolio_before={},
            investor_response="MAYBE",
        )


def test_investor_override_and_note_recorded():
    entry = engine.build_decision_journal_entry(
        ai_cio_decision=sample_decision(),
        portfolio_before={"AMDW + PLTU": 100.0},
        investor_response="OVERRIDDEN",
        investor_note="Remain in the current allocation.",
    )
    assert entry["investor_response"] == "OVERRIDDEN"
    assert entry["investor_note"] == "Remain in the current allocation."


def test_append_preserves_prior_entries(tmp_path: Path):
    path = tmp_path / "decision_journal.json"
    first = engine.build_decision_journal_entry(
        ai_cio_decision=sample_decision(), portfolio_before={"A": 100}
    )
    second = engine.build_decision_journal_entry(
        ai_cio_decision=sample_decision(), portfolio_before={"A": 100}
    )
    engine.append_decision_journal_entry(first, journal_path=str(path))
    journal = engine.append_decision_journal_entry(second, journal_path=str(path))
    assert journal["entry_count"] == 2
    assert journal["entries"][0]["entry_id"] == first["entry_id"]
    assert journal["entries"][1]["entry_id"] == second["entry_id"]


def test_write_outputs_json_and_markdown(tmp_path: Path):
    entry = engine.build_decision_journal_entry(
        ai_cio_decision=sample_decision(),
        portfolio_before={"AMDW + PLTU": 100.0},
    )
    result = engine.write_decision_journal(entry, root_path=str(tmp_path))
    assert result["entry_count"] == 1
    assert (tmp_path / "decision_journal.json").exists()
    assert (tmp_path / "decision_journal.md").exists()


def test_markdown_uses_full_score_names():
    entry = engine.build_decision_journal_entry(
        ai_cio_decision=sample_decision(), portfolio_before={}
    )
    markdown = engine.format_decision_journal_markdown([entry])
    assert "Decision Stability Score" in markdown
    assert "Evidence Confidence" in markdown
    assert "DSS" not in markdown
    assert "CES" not in markdown


def test_paper_only_flags_are_enforced():
    entry = engine.build_decision_journal_entry(
        ai_cio_decision=sample_decision(), portfolio_before={}
    )
    assert entry["paper_trade_mode"] is True
    assert entry["live_trading_enabled"] is False
    assert entry["broker_execution_enabled"] is False
    assert entry["reporting_only"] is True


def test_previous_entry_link_is_recorded():
    entry = engine.build_decision_journal_entry(
        ai_cio_decision=sample_decision(),
        portfolio_before={},
        previous_entry_id="prior-123",
    )
    assert entry["previous_entry_id"] == "prior-123"


def test_source_contains_no_restricted_execution_calls():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    forbidden = ["os.system(", "subprocess.", "place_order(", "execute_trade(", "robin_stocks"]
    for token in forbidden:
        assert token not in source
