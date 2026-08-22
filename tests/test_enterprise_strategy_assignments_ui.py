import json
from pathlib import Path

from src.dividend_bot.enterprise_manual_strategy_ui import render_manual_strategy_panel
from src.dividend_bot.enterprise_strategy_assignments_ui import render_strategy_assignments_panel


def _row(root: Path) -> dict:
    return {
        "strategy_id": "SWING-001",
        "evidence_root": str(root),
        "capabilities": ["manual_strategy"],
        "published_artifacts": [
            {
                "artifact_type": "manual_strategy",
                "path": "results/manual_entry_strategy_form_contract.json",
            }
        ],
    }


def test_strategy_assignments_tab_shows_direct_shadow_metrics_and_only_promotion_control(tmp_path: Path) -> None:
    (tmp_path / "results").mkdir()
    (tmp_path / "results/strategy_assignment_shadow_report.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "strategy_id": "SWING-001",
                "paper_trade_mode": True,
                "auto_promotion_enabled": False,
                "rows": [
                    {
                        "underlying_symbol": "NFLX",
                        "direct_strategy_id": "DIRECT_A",
                        "direct_strategy_name": "Direct A",
                        "current_swing_allocation": 600.0,
                        "shadow_strategies": [
                            {
                                "strategy_id": "SHADOW_B",
                                "strategy_name": "Shadow B",
                                "timeframe": "1D",
                                "simulated_allocation": 600.0,
                                "trade_count": 8,
                                "win_rate": 62.5,
                                "net_pl": 75.0,
                                "max_drawdown": -18.0,
                                "profit_factor": 2.1,
                                "promotion_recommended": True,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = render_strategy_assignments_panel(_row(tmp_path))
    assert "NFLX" in output
    assert "Direct A" in output
    assert "Shadow B" in output
    assert "$600.00" in output
    assert "$75.00" in output
    assert "$-18.00" in output
    assert "PROMOTION RECOMMENDED" in output
    assert "action='/strategy/shadow-promote'" in output
    assert ">Promote</button>" in output
    assert "No automatic replacement" in output


def test_manual_strategy_form_has_assignment_mode_but_no_promotion_button(tmp_path: Path) -> None:
    (tmp_path / "results").mkdir()
    (tmp_path / "results/manual_entry_strategy_form_contract.json").write_text(
        json.dumps(
            {
                "schema_version": "1.3",
                "strategy_id": "SWING-001",
                "paper_trade_mode": True,
                "allocation_authority": "SWING_PORTFOLIO_ALLOCATOR",
                "fields": [
                    {"name": "assignment_mode", "choices": ["DIRECT", "SHADOW"], "help": "Direct or shadow", "example": "SHADOW"},
                    {"name": "direction", "choices": ["LONG"]},
                    {"name": "timeframe", "choices": ["1D"]},
                    {"name": "rule_logic", "choices": ["ALL", "ANY"]},
                    {"name": "regime_logic", "choices": ["ALL", "ANY"]},
                    {"name": "rules", "operator_choices": [">"]},
                    {"name": "regime_filters", "operator_choices": [">"]},
                ],
                "current_registry": {"strategies": [], "assignments": []},
                "submission_contract": {"status": "AVAILABLE"},
            }
        ),
        encoding="utf-8",
    )
    output = render_manual_strategy_panel(_row(tmp_path))
    assert "name='assignment_mode'" in output
    assert "DIRECT" in output and "SHADOW" in output
    assert "Save Strategy" in output
    assert "/strategy/shadow-promote" not in output
    assert ">Promote</button>" not in output
