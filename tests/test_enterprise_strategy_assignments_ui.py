import json
from pathlib import Path

from src.dividend_bot.enterprise_manual_strategy_ui import render_manual_strategy_panel
from src.dividend_bot.enterprise_strategy_assignments_ui import (
    ASSIGNMENT_ARTIFACT_ID,
    ASSIGNMENT_ARTIFACT_TYPE,
    MAX_SHADOWS,
    load_strategy_assignment_report,
    render_strategy_assignments_panel,
)


EXPECTED_STACKS = {
    "SOXL": ("SOXL_BIGBELUGA_1H_PRIMARY", ["SOXL_ZERO_LAG_1H_SHADOW_1", "SOXL_ZERO_LAG_4H_SHADOW_2"]),
    "TQQQ": ("TQQQ_QQQ_BIGBELUGA_1H_PRIMARY", ["TQQQ_QQQ_ZERO_LAG_1H_SHADOW_1", "TQQQ_QQQ_VOL_VIDYA_1H_SHADOW_2"]),
    "NFLU": ("NFLU_NFLX_ZERO_LAG_1H_PRIMARY", ["NFLU_NFLX_STRATEGY_F_1H_SHADOW_1", "NFLU_NFLX_KELTNER_1H_SHADOW_2", "NFLU_NFLX_VOL_VIDYA_1H_SHADOW_3"]),
    "NVDX": ("NVDX_NVDA_STRATEGY_F_1H_PRIMARY", ["NVDX_NVDA_ZERO_LAG_BALANCE_1H_SHADOW_1", "NVDX_NVDA_KELTNER_1H_SHADOW_2", "NVDX_NVDA_ZERO_LAG_PROFIT_1H_SHADOW_3"]),
    "PLTU": ("PLTU_PLTR_BIGBELUGA_RANGE_1H_PRIMARY", ["PLTU_PLTR_KELTNER_1H_SHADOW_1", "PLTU_PLTR_STRATEGY_F_4H_SHADOW_2", "PLTU_PLTR_AI_C2_4H_SHADOW_3", "PLTU_PLTR_AI_C1_1H_SHADOW_4"]),
    "AMZU": ("AMZU_AMZN_KELTNER_4H_PRIMARY", ["AMZU_AMZN_AI_C2_4H_SHADOW_1", "AMZU_AMZN_BIGBELUGA_1H_SHADOW_2", "AMZU_AMZN_STRATEGY_F_1H_SHADOW_3", "AMZU_AMZN_AI_C1_DAILY_SHADOW_4"]),
    "GGLL": ("GGLL_GOOG_STRATEGY_F_1H_PRIMARY", ["GGLL_GOOG_ZERO_LAG_1H_SHADOW_1", "GGLL_GOOG_ZERO_LAG_4H_SHADOW_2", "GGLL_GOOG_AI_C2_4H_SHADOW_3"]),
    "AMDL": ("AMDL_AMD_AI_C2_QUALITY_1H_PRIMARY", ["AMDL_AMD_AI_C2_PROFIT_1H_SHADOW_1", "AMDL_AMD_ZERO_LAG_BALANCE_1H_SHADOW_2", "AMDL_AMD_AI_C1_DAILY_SHADOW_3", "AMDL_AMD_ZERO_LAG_NATIVE_1H_SHADOW_4"]),
    "AVL": ("AVL_AVGO_ZERO_LAG_BALANCE_1H_PRIMARY", ["AVL_AVGO_AI_C1_DAILY_SHADOW_1", "AVL_AVGO_KELTNER_1H_SHADOW_2", "AVL_AVGO_STRATEGY_F_1H_SHADOW_3", "AVL_AVGO_AI_C2_DAILY_SHADOW_4"]),
}


def _row(root: Path, *, include_assignment_artifact: bool = True) -> dict:
    artifacts = [
        {
            "artifact_id": "manual_entry_strategy_form_contract",
            "artifact_type": "manual_strategy",
            "path": "results/manual_entry_strategy_form_contract.json",
        }
    ]
    if include_assignment_artifact:
        artifacts.append(
            {
                "artifact_id": ASSIGNMENT_ARTIFACT_ID,
                "artifact_type": ASSIGNMENT_ARTIFACT_TYPE,
                "path": "results/enterprise_strategy_assignments.json",
                "format": "JSON",
                "authoritative": True,
                "required": False,
            }
        )
    return {
        "strategy_id": "SWING-001",
        "evidence_root": str(root),
        "capabilities": ["manual_strategy", "strategy_assignments"],
        "published_artifacts": artifacts,
        "allocated_capital": 0.0,
        "holdings": [],
    }


def _assignment_payload() -> dict:
    symbols = [
        {
            "symbol": symbol,
            "research_status": "FROZEN_DEPLOYMENT_STACK",
            "primary_strategy_id": primary,
            "shadow_strategy_ids": list(shadows),
        }
        for symbol, (primary, shadows) in EXPECTED_STACKS.items()
    ]
    strategies = []
    signal_by_symbol = {
        "TQQQ": "QQQ",
        "NFLU": "NFLX",
        "NVDX": "NVDA",
        "PLTU": "PLTR",
        "AMZU": "AMZN",
        "GGLL": "GOOG",
        "AMDL": "AMD",
        "AVL": "AVGO",
        "SOXL": "SOXL",
    }
    for symbol, (primary, shadows) in EXPECTED_STACKS.items():
        for index, strategy_id in enumerate([primary, *shadows]):
            strategies.append(
                {
                    "strategy_id": strategy_id,
                    "name": f"{symbol} Strategy {index}",
                    "signal_symbol": signal_by_symbol[symbol],
                    "vehicle_symbol": symbol,
                    "timeframe": "1H" if symbol != "AMZU" else "4H",
                    "engine_id": "TEST_ENGINE",
                    "assignment_mode": "DIRECT" if index == 0 else "SHADOW",
                    "paper_trade_mode": True,
                    "frozen_checkpoint": {
                        "backtest_period": "2023-01-01_to_2026-08-28",
                        "trade_count": 20 + index,
                        "win_rate_percent": 60.0 + index,
                        "net_pl_dollars": 10.0 + index,
                        "profit_factor": 2.0 + index / 10,
                        "max_drawdown_dollars": 5.0 + index,
                    },
                }
            )
    return {
        "schema_version": "1.1",
        "strategy_id": "SWING-001",
        "paper_trade_mode": True,
        "symbols": symbols,
        "strategies": strategies,
    }


def _write_assignment_artifact(root: Path, payload: dict | None = None) -> Path:
    path = root / "results/enterprise_strategy_assignments.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload or _assignment_payload()), encoding="utf-8")
    return path


def test_ai_cio_discovers_exactly_one_registered_swing_assignment_artifact(tmp_path: Path) -> None:
    row = _row(tmp_path)
    matches = [
        item
        for item in row["published_artifacts"]
        if item.get("artifact_id") == ASSIGNMENT_ARTIFACT_ID
        and item.get("artifact_type") == ASSIGNMENT_ARTIFACT_TYPE
    ]
    assert len(matches) == 1
    assert matches[0]["path"] == "results/enterprise_strategy_assignments.json"


def test_loads_registered_enterprise_strategy_assignments_artifact(tmp_path: Path) -> None:
    _write_assignment_artifact(tmp_path)
    report, status = load_strategy_assignment_report(_row(tmp_path))
    assert status == "AVAILABLE"
    assert report is not None
    assert len(report["symbols"]) == 9
    assert report["strategy_id"] == "SWING-001"


def test_all_nine_published_stacks_and_order_are_preserved(tmp_path: Path) -> None:
    _write_assignment_artifact(tmp_path)
    report, status = load_strategy_assignment_report(_row(tmp_path))
    assert status == "AVAILABLE"
    assert report is not None
    actual = {
        item["symbol"]: (item["primary_strategy_id"], item["shadow_strategy_ids"])
        for item in report["symbols"]
    }
    assert actual == EXPECTED_STACKS
    assert max(len(shadows) for _, shadows in actual.values()) == MAX_SHADOWS
    assert all(len(shadows) <= 4 for _, shadows in actual.values())


def test_strategy_metadata_joins_from_published_strategies_collection(tmp_path: Path) -> None:
    _write_assignment_artifact(tmp_path)
    output = render_strategy_assignments_panel(_row(tmp_path))
    assert "TQQQ Strategy 0" in output
    assert "QQQ" in output
    assert "TQQQ" in output
    assert "TEST_ENGINE" in output
    assert "DIRECT" in output
    assert "2023-01-01_to_2026-08-28" in output
    assert "60.0%" in output
    assert "$10.00" in output


def test_assignments_are_independent_of_allocation_and_holdings(tmp_path: Path) -> None:
    _write_assignment_artifact(tmp_path)
    row = _row(tmp_path)
    row["allocated_capital"] = 0.0
    row["position_count"] = 0
    row["holdings"] = []
    output = render_strategy_assignments_panel(row)
    for symbol in EXPECTED_STACKS:
        assert symbol in output
    assert "AMZU_AMZN_KELTNER_4H_PRIMARY" in output


def test_missing_registered_artifact_is_explicitly_unavailable_without_legacy_fallback(tmp_path: Path) -> None:
    (tmp_path / "results").mkdir()
    (tmp_path / "results/strategy_assignment_shadow_report.json").write_text(
        json.dumps(
            {
                "strategy_id": "SWING-001",
                "paper_trade_mode": True,
                "rows": [{"underlying_symbol": "STALE", "shadow_strategies": []}],
            }
        ),
        encoding="utf-8",
    )
    output = render_strategy_assignments_panel(_row(tmp_path))
    assert "Strategy assignment evidence unavailable" in output
    assert "ASSIGNMENT_ARTIFACT_MISSING" in output
    assert "STALE" not in output
    assert "No Shadow strategies assigned" not in output
    assert "does not fall back to legacy assignment, allocation, or holdings data" in output


def test_undeclared_artifact_does_not_use_file_even_if_present(tmp_path: Path) -> None:
    _write_assignment_artifact(tmp_path)
    output = render_strategy_assignments_panel(_row(tmp_path, include_assignment_artifact=False))
    assert "ASSIGNMENT_ARTIFACT_NOT_DECLARED" in output
    assert "SOXL_BIGBELUGA_1H_PRIMARY" not in output


def test_shadow_five_is_rejected_by_governance_boundary(tmp_path: Path) -> None:
    payload = _assignment_payload()
    payload["symbols"][0]["shadow_strategy_ids"] = ["S1", "S2", "S3", "S4", "S5"]
    _write_assignment_artifact(tmp_path, payload)
    report, status = load_strategy_assignment_report(_row(tmp_path))
    assert report is None
    assert status == "SHADOW_GOVERNANCE_LIMIT_EXCEEDED"


def test_strategy_assignments_render_primary_shadows_and_user_only_promotion_controls(tmp_path: Path) -> None:
    _write_assignment_artifact(tmp_path)
    output = render_strategy_assignments_panel(_row(tmp_path))
    assert "SOXL" in output
    assert "SOXL_BIGBELUGA_1H_PRIMARY" in output
    assert "SOXL_ZERO_LAG_1H_SHADOW_1" in output
    assert "2 Shadows" in output
    assert "PRIMARY" in output
    assert "SHADOW" in output
    assert "USER PROMOTION ONLY" in output
    assert "action='/strategy/shadow-promote'" in output
    assert ">Promote</button>" in output
    assert "No automatic replacement" in output


def test_consumer_is_read_only_and_does_not_modify_authoritative_artifact(tmp_path: Path) -> None:
    path = _write_assignment_artifact(tmp_path)
    original = path.read_text(encoding="utf-8")
    render_strategy_assignments_panel(_row(tmp_path))
    assert path.read_text(encoding="utf-8") == original


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
    output = render_manual_strategy_panel(_row(tmp_path, include_assignment_artifact=False))
    assert "name='assignment_mode'" in output
    assert "DIRECT" in output and "SHADOW" in output
    assert "Save Strategy" in output
    assert "/strategy/shadow-promote" not in output
    assert ">Promote</button>" not in output
