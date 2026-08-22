import json
from pathlib import Path

from src.dividend_bot.enterprise_manual_strategy_ui import render_manual_strategy_panel
from src.dividend_bot.enterprise_portal_strategy_ui_v2 import render_strategy_workspace


def _rule_field(name, help_text, example):
    return {
        "name": name,
        "operator_choices": [">", "<", "between"],
        "smoothing_choices": ["EMA", "SMA", "WILDER"],
        "price_source_choices": ["CLOSE", "OHLC_AVERAGE"],
        "help": help_text,
        "example": example,
    }


def _contract(path: Path, *, status: str = "INTAKE_HANDLER_PENDING") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        {"name": "name", "help": "Friendly name shown to the user.", "example": "M-HMA50 Daily"},
        {"name": "strategy_id", "help": "Permanent strategy identifier.", "example": "M_HMA50_DAILY"},
        {"name": "underlying_symbol", "help": "Ticker used to generate the signal.", "example": "NFLX"},
        {"name": "assignment_mode", "choices": ["DIRECT", "SHADOW"], "help": "Direct or shadow assignment.", "example": "DIRECT"},
        {"name": "execution_symbol", "help": "Read-only verified mapping.", "example": "NFLX → NFLU"},
        {"name": "timeframe", "choices": ["1D", "4H"], "help": "Bar interval.", "example": "1D"},
        {"name": "direction", "choices": ["LONG"], "help": "Trade direction.", "example": "LONG"},
        {"name": "session", "help": "Bar construction session.", "example": "08:30-14:30 CT"},
        {"name": "number_of_entries", "help": "Staged purchase count.", "example": "1 for M-HMA50"},
        {"name": "confirmation_bars", "help": "Consecutive qualifying completed bars.", "example": "2 for M-HMA50 Daily"},
        {"name": "rule_logic", "choices": ["ALL", "ANY"], "help": "Entry rule combination.", "example": "ALL"},
        _rule_field("rules", "Entry conditions with explicit indicator parameters.", "close > keltner_middle, period 14, factor 1"),
        {"name": "regime_logic", "choices": ["ALL", "ANY"], "help": "Regime combination.", "example": "ALL"},
        _rule_field("regime_filters", "Regime requirements.", "chop < 60, period 14"),
        {"name": "normal_exit_logic", "choices": ["ALL", "ANY"], "help": "Always-active exit combination.", "example": "ANY"},
        _rule_field("normal_exit_rules", "Always-active exit rules.", "close < ema, period 18"),
        {"name": "conditional_exit_enabled", "help": "Enable profit-conditional exit.", "example": "Enabled"},
        {"name": "conditional_exit_pl_threshold", "help": "Profit gate threshold.", "example": "0"},
        _rule_field("conditional_exit_rules", "Rules evaluated after profit gate.", "close < hma, period 50"),
        {"name": "conditional_exit_cooldown_bars", "help": "Cooldown after conditional exit.", "example": "2"},
        {"name": "conditional_exit_cooldown_unit", "choices": ["TRADING_DAY", "BAR"], "help": "Cooldown unit.", "example": "TRADING_DAY"},
        {"name": "exit_policy_id", "help": "Optional existing exit policy.", "example": "Leave blank"},
        {"name": "allocation_authority", "help": "Swing controls allocation dollars.", "example": "SWING_PORTFOLIO_ALLOCATOR"},
        {"name": "paper_trade_mode", "help": "Mandatory paper-only safety mode.", "example": "TRUE"},
    ]
    path.write_text(json.dumps({
        "schema_version": "1.4",
        "strategy_id": "SWING-001",
        "form_id": "SWING_MANUAL_TRADING_STRATEGY",
        "display_name": "Manual Strategy",
        "paper_trade_mode": True,
        "allocation_authority": "SWING_PORTFOLIO_ALLOCATOR",
        "fields": fields,
        "current_registry": {
            "strategies": [{"strategy_id": "TEST", "name": "Test Strategy", "timeframe": "1D", "number_of_entries": 1, "confirmation_bars": 2}],
            "assignments": [{"underlying_symbol": "NFLX", "strategy_id": "TEST", "assignment_mode": "DIRECT"}],
        },
        "submission_contract": {"status": status},
    }), encoding="utf-8")


def _swing_row(root: Path) -> dict:
    return {
        "strategy_id": "SWING-001", "display_name": "Trade Swing Bot", "allocated_capital": 4500,
        "health_status": "HEALTHY", "evidence_status": "AVAILABLE", "capability_count": 1,
        "published_artifact_count": 1, "capabilities": ["manual_strategy"],
        "published_artifacts": [{"artifact_id": "manual_entry_strategy_form_contract", "artifact_type": "manual_strategy", "path": "results/manual_entry_strategy_form_contract.json", "format": "json", "authoritative": True, "required": False}],
        "evidence_root": str(root),
    }


def test_manual_strategy_panel_reads_swing_declared_contract(tmp_path: Path) -> None:
    _contract(tmp_path / "results/manual_entry_strategy_form_contract.json")
    output = render_manual_strategy_panel(_swing_row(tmp_path))
    assert "Manual Trading Strategy" in output
    assert "Consecutive Qualifying Bars" in output
    assert "Normal Exit Rules" in output
    assert "Conditional / Profit-Activated Exit" in output
    assert "SWING_PORTFOLIO_ALLOCATOR" in output
    assert "Save unavailable" in output


def test_manual_strategy_panel_explains_frozen_indicator_parameters(tmp_path: Path) -> None:
    _contract(tmp_path / "results/manual_entry_strategy_form_contract.json", status="AVAILABLE")
    output = render_manual_strategy_panel(_swing_row(tmp_path))
    assert "Frozen-strategy friendly" in output
    assert "Factor" in output
    assert "Smoothing" in output
    assert "Price Source" in output
    assert "OHLC_AVERAGE" in output
    assert "M_HMA50_DAILY" in output


def test_manual_strategy_form_posts_full_lifecycle_rule_arrays(tmp_path: Path) -> None:
    _contract(tmp_path / "results/manual_entry_strategy_form_contract.json", status="AVAILABLE")
    output = render_manual_strategy_panel(_swing_row(tmp_path))
    for prefix in ("entry_rule", "regime_rule", "normal_exit_rule", "conditional_exit_rule"):
        assert f"name='{prefix}_left'" in output
        assert f"name='{prefix}_operator'" in output
        assert f"name='{prefix}_right'" in output
        assert f"name='{prefix}_period'" in output
        assert f"name='{prefix}_factor'" in output
        assert f"name='{prefix}_smoothing'" in output
        assert f"name='{prefix}_price_source'" in output
    assert "name='confirmation_bars'" in output
    assert "name='conditional_exit_pl_threshold'" in output
    assert "name='conditional_exit_cooldown_bars'" in output


def test_swing_workspace_receives_manual_strategy_tab_only_when_capability_declared(tmp_path: Path) -> None:
    _contract(tmp_path / "results/manual_entry_strategy_form_contract.json")
    output = render_strategy_workspace({"strategy_kpis": [_swing_row(tmp_path)]}, audience="executive")
    assert "data-workspace-tab-target='manual-strategy'" in output
    assert "Manual Strategy</button>" in output
    assert "Manual Trading Strategy" in output


def test_dividend_workspace_does_not_receive_swing_manual_strategy_tab(tmp_path: Path) -> None:
    row = _swing_row(tmp_path)
    row["strategy_id"] = "DIVIDEND-001"
    output = render_strategy_workspace({"strategy_kpis": [row]}, audience="executive")
    assert "data-workspace-tab-target='manual-strategy'" not in output


def test_manual_form_save_enables_only_after_swing_intake_is_available(tmp_path: Path) -> None:
    _contract(tmp_path / "results/manual_entry_strategy_form_contract.json", status="AVAILABLE")
    output = render_manual_strategy_panel(_swing_row(tmp_path))
    assert ">Save Strategy</button>" in output
    assert "Save unavailable" not in output
