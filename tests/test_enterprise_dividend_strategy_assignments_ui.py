import json

from src.dividend_bot.enterprise_dividend_strategy_assignments_ui import (
    dividend_strategy_assignments_css,
    render_dividend_strategy_assignments,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dividend_assignments_render_primary_and_shadow(tmp_path):
    _write_json(
        tmp_path / "state/dividend_pair_strategy_assignments.json",
        {
            "assignments": {
                "AMDW / AMDL": {
                    "primary_strategy": "STRATEGY_A",
                    "shadow_strategies": ["STRATEGY_B"],
                }
            }
        },
    )

    _write_json(
        tmp_path / "results/dividend_strategy_shadow_performance.json",
        {
            "performance": [
                {
                    "pair": "AMDW / AMDL",
                    "strategy_id": "STRATEGY_A",
                    "display_name": "Strategy A",
                    "virtual_capital_basis": 750,
                    "current_shadow_value": 800,
                    "total_return_percent": 6.67,
                    "virtual_gain_loss": 50,
                    "max_drawdown_percent": 3.5,
                    "completed_trade_count": 2,
                    "observation_count": 100,
                    "last_action": "SHADOW_HOLD",
                },
                {
                    "pair": "AMDW / AMDL",
                    "strategy_id": "STRATEGY_B",
                    "display_name": "Strategy B",
                    "virtual_capital_basis": 750,
                    "current_shadow_value": 825,
                    "total_return_percent": 10,
                    "virtual_gain_loss": 75,
                    "max_drawdown_percent": 3,
                    "completed_trade_count": 2,
                    "observation_count": 100,
                    "last_action": "SHADOW_HOLD",
                },
            ]
        },
    )

    html = render_dividend_strategy_assignments(tmp_path)

    assert "Dividend Strategy Assignments" in html
    assert "AMDW / AMDL" in html
    assert "STRATEGY_A" in html
    assert "STRATEGY_B" in html
    assert "PRIMARY" in html
    assert "SHADOW" in html
    assert "PAPER ONLY" in html


def test_dividend_assignments_show_pending_owner_review(tmp_path):
    _write_json(
        tmp_path / "state/dividend_pair_strategy_assignments.json",
        {
            "assignments": {
                "AMDW / AMDL": {
                    "primary_strategy": "STRATEGY_A",
                    "shadow_strategies": ["STRATEGY_B"],
                }
            }
        },
    )

    _write_json(
        tmp_path / "state/dividend_strategy_promotion_requests.json",
        {
            "requests": [
                {
                    "pair": "AMDW / AMDL",
                    "status": "PENDING_OWNER_REVIEW",
                    "current_primary_strategy": "STRATEGY_A",
                    "proposed_primary_strategy": "STRATEGY_B",
                    "veto_deadline": "2026-08-30",
                }
            ]
        },
    )

    html = render_dividend_strategy_assignments(tmp_path)

    assert "Promotion review pending" in html
    assert "STRATEGY_B" in html
    assert "STRATEGY_A" in html
    assert "2026-08-30" in html
    assert "veto" in html.lower()


def test_dividend_assignments_do_not_expose_execution_controls(tmp_path):
    _write_json(
        tmp_path / "state/dividend_pair_strategy_assignments.json",
        {
            "assignments": {
                "AMDW / AMDL": {
                    "primary_strategy": "STRATEGY_A",
                    "shadow_strategies": ["STRATEGY_B"],
                }
            }
        },
    )

    html = render_dividend_strategy_assignments(tmp_path)

    assert "PAPER ONLY" in html
    assert "place orders" in html
    assert "broker_execution" not in html
    assert "shadow-promote" not in html


def test_dividend_assignment_css_is_available():
    css = dividend_strategy_assignments_css()

    assert ".dividend-strategy-assignments" in css
    assert ".dividend-assignment-role.primary" in css
    assert ".dividend-assignment-role.shadow" in css
