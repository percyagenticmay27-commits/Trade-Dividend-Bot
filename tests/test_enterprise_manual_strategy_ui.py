import json
from pathlib import Path

from src.dividend_bot.enterprise_manual_strategy_ui import render_manual_strategy_panel
from src.dividend_bot.enterprise_portal_strategy_ui_v2 import render_strategy_workspace


def _contract(path: Path, *, status: str = "INTAKE_HANDLER_PENDING") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "strategy_id": "SWING-001",
                "form_id": "SWING_MANUAL_ENTRY_STRATEGY",
                "display_name": "Manual Strategy",
                "paper_trade_mode": True,
                "allocation_authority": "SWING_PORTFOLIO_ALLOCATOR",
                "fields": [
                    {"name": "timeframe", "choices": ["1D", "4H"]},
                    {"name": "direction", "choices": ["LONG"]},
                    {"name": "rule_logic", "choices": ["ALL", "ANY"]},
                    {"name": "rules", "operator_choices": [">", "<", "between"]},
                    {"name": "regime_logic", "choices": ["ALL", "ANY"]},
                    {"name": "regime_filters", "operator_choices": [">", "<", "between"]},
                ],
                "current_registry": {
                    "strategies": [
                        {
                            "strategy_id": "TEST",
                            "name": "Test Strategy",
                            "timeframe": "1D",
                            "number_of_entries": 3,
                        }
                    ],
                    "assignments": [
                        {"underlying_symbol": "NFLX", "strategy_id": "TEST"}
                    ],
                },
                "submission_contract": {"status": status},
            }
        ),
        encoding="utf-8",
    )


def _swing_row(root: Path) -> dict:
    return {
        "strategy_id": "SWING-001",
        "display_name": "Trade Swing Bot",
        "allocated_capital": 4500,
        "health_status": "HEALTHY",
        "evidence_status": "AVAILABLE",
        "capability_count": 1,
        "published_artifact_count": 1,
        "capabilities": ["manual_strategy"],
        "published_artifacts": [
            {
                "artifact_id": "manual_entry_strategy_form_contract",
                "artifact_type": "manual_strategy",
                "path": "results/manual_entry_strategy_form_contract.json",
                "format": "json",
                "authoritative": True,
                "required": False,
            }
        ],
        "evidence_root": str(root),
    }


def test_manual_strategy_panel_reads_swing_declared_contract(tmp_path: Path) -> None:
    _contract(tmp_path / "results/manual_entry_strategy_form_contract.json")
    output = render_manual_strategy_panel(_swing_row(tmp_path))

    assert "Manual Strategy Entry" in output
    assert "Number of Entries" in output
    assert "SWING_PORTFOLIO_ALLOCATOR" in output
    assert "NFLX" in output
    assert "Test Strategy" in output
    assert "structured rules" in output
    assert "Save unavailable" in output


def test_manual_strategy_form_posts_named_structured_rule_arrays(tmp_path: Path) -> None:
    _contract(tmp_path / "results/manual_entry_strategy_form_contract.json", status="AVAILABLE")
    output = render_manual_strategy_panel(_swing_row(tmp_path))

    assert "action='/strategy/manual-entry'" in output
    assert "name='entry_rule_left'" in output
    assert "name='entry_rule_operator'" in output
    assert "name='entry_rule_right'" in output
    assert "name='entry_rule_period'" in output
    assert "name='regime_rule_left'" in output
    assert "name='regime_rule_operator'" in output
    assert "name='regime_rule_right'" in output
    assert "name='regime_rule_period'" in output
    assert "data-add-manual-rule='entry'" in output
    assert "data-add-manual-rule='regime'" in output


def test_swing_workspace_receives_manual_strategy_tab_only_when_capability_declared(tmp_path: Path) -> None:
    _contract(tmp_path / "results/manual_entry_strategy_form_contract.json")
    report = {"strategy_kpis": [_swing_row(tmp_path)]}
    output = render_strategy_workspace(report, audience="executive")

    assert "data-workspace-tab-target='manual-strategy'" in output
    assert "Manual Strategy</button>" in output
    assert "id='panel-SWING-001-manual-strategy'" in output
    assert "Manual Strategy Entry" in output


def test_dividend_workspace_does_not_receive_swing_manual_strategy_tab(tmp_path: Path) -> None:
    row = _swing_row(tmp_path)
    row["strategy_id"] = "DIVIDEND-001"
    row["display_name"] = "Dividend Income Strategy"
    report = {"strategy_kpis": [row]}

    output = render_strategy_workspace(report, audience="executive")
    assert "data-workspace-tab-target='manual-strategy'" not in output


def test_manual_form_save_enables_only_after_swing_intake_is_available(tmp_path: Path) -> None:
    _contract(tmp_path / "results/manual_entry_strategy_form_contract.json", status="AVAILABLE")
    output = render_manual_strategy_panel(_swing_row(tmp_path))

    assert ">Save Strategy</button>" in output
    assert "Save unavailable" not in output
