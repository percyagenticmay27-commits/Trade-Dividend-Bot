from pathlib import Path

import pytest

from src.dividend_bot.enterprise_dividend_daily_cycle_integration import (
    ADVISORY_ONLY,
    BROKER_EXECUTION_ENABLED,
    LIVE_TRADING_ENABLED,
    ORCHESTRATION_ONLY,
    PAPER_TRADE_MODE,
    STEP_ORDER,
    build_and_write_enterprise_dividend_daily_cycle,
    build_enterprise_dividend_daily_cycle,
    default_daily_cycle_steps,
    render_enterprise_dividend_daily_cycle_markdown,
    write_enterprise_dividend_daily_cycle,
)

FIXED_TIME = "2026-07-25T15:30:00Z"


def test_safety_constants_are_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert ADVISORY_ONLY is True
    assert ORCHESTRATION_ONLY is True


def test_default_steps_follow_required_dependency_order():
    steps = default_daily_cycle_steps()
    assert [item["step_name"] for item in steps] == list(STEP_ORDER)
    assert [item["sequence"] for item in steps] == list(range(1, len(STEP_ORDER) + 1))


def test_default_first_step_has_no_dependency():
    assert default_daily_cycle_steps()[0]["dependencies"] == []


def test_default_later_steps_depend_on_previous_step():
    steps = default_daily_cycle_steps()
    for index in range(1, len(steps)):
        assert steps[index]["dependencies"] == [steps[index - 1]["step_name"]]


def test_empty_custom_steps_produce_valid_empty_plan():
    report = build_enterprise_dividend_daily_cycle(steps=[], generated_at_utc=FIXED_TIME)
    assert report["cycle_status"] == "COMPLETED"
    assert report["summary"]["total_steps"] == 0


def test_default_plan_is_planned_without_results():
    report = build_enterprise_dividend_daily_cycle(generated_at_utc=FIXED_TIME)
    assert report["cycle_status"] == "PLANNED"
    assert report["summary"]["pending_steps"] == len(STEP_ORDER)


def test_fixed_inputs_are_deterministic():
    first = build_enterprise_dividend_daily_cycle(generated_at_utc=FIXED_TIME)
    second = build_enterprise_dividend_daily_cycle(generated_at_utc=FIXED_TIME)
    assert first == second


def test_reporting_period_changes_cycle_identity():
    first = build_enterprise_dividend_daily_cycle(reporting_period="2026-07-25", generated_at_utc=FIXED_TIME)
    second = build_enterprise_dividend_daily_cycle(reporting_period="2026-07-26", generated_at_utc=FIXED_TIME)
    assert first["cycle_id"] != second["cycle_id"]


def test_duplicate_steps_are_rejected():
    steps = [{"step_name": "INCOME"}, {"step_name": "INCOME"}]
    with pytest.raises(ValueError, match="Duplicate"):
        build_enterprise_dividend_daily_cycle(steps=steps, generated_at_utc=FIXED_TIME)


def test_unknown_step_is_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        build_enterprise_dividend_daily_cycle(steps=[{"step_name": "BROKER_ORDER"}], generated_at_utc=FIXED_TIME)


def test_unknown_dependency_is_rejected():
    with pytest.raises(ValueError, match="Unsupported dependencies"):
        build_enterprise_dividend_daily_cycle(
            steps=[{"step_name": "INCOME", "dependencies": ["UNKNOWN"]}],
            generated_at_utc=FIXED_TIME,
        )


def test_forward_dependency_is_rejected():
    with pytest.raises(ValueError, match="forward dependency"):
        build_enterprise_dividend_daily_cycle(
            steps=[{"step_name": "INCOME", "dependencies": ["FORECAST"]}],
            generated_at_utc=FIXED_TIME,
        )


def test_custom_steps_are_sorted_by_platform_order():
    report = build_enterprise_dividend_daily_cycle(
        steps=[{"step_name": "FORECAST"}, {"step_name": "INCOME"}],
        generated_at_utc=FIXED_TIME,
    )
    assert [item["step_name"] for item in report["steps"]] == ["INCOME", "FORECAST"]


def test_missing_input_artifacts_create_warnings_not_failure():
    report = build_enterprise_dividend_daily_cycle(
        steps=[{"step_name": "INCOME", "input_artifacts": ["lifecycle.json"]}],
        generated_at_utc=FIXED_TIME,
    )
    assert report["summary"]["warning_count"] == 1
    assert report["cycle_status"] == "PLANNED"


def test_available_input_artifacts_remove_warning():
    report = build_enterprise_dividend_daily_cycle(
        steps=[{"step_name": "INCOME", "input_artifacts": ["lifecycle.json"]}],
        available_artifacts=["lifecycle.json"],
        generated_at_utc=FIXED_TIME,
    )
    assert report["warnings"] == []


def test_all_completed_results_complete_cycle():
    results = {name: {"status": "COMPLETED"} for name in STEP_ORDER}
    report = build_enterprise_dividend_daily_cycle(step_results=results, generated_at_utc=FIXED_TIME)
    assert report["cycle_status"] == "COMPLETED"
    assert report["summary"]["completed_steps"] == len(STEP_ORDER)


def test_warning_result_completes_with_warnings():
    steps = [{"step_name": "LIFECYCLE"}]
    report = build_enterprise_dividend_daily_cycle(
        steps=steps,
        step_results={"LIFECYCLE": {"status": "WARNING", "message": "partial"}},
        generated_at_utc=FIXED_TIME,
    )
    assert report["cycle_status"] == "COMPLETED_WITH_WARNINGS"
    assert report["summary"]["warning_steps"] == 1


def test_failed_result_marks_cycle_failed():
    steps = [{"step_name": "LIFECYCLE"}]
    report = build_enterprise_dividend_daily_cycle(
        steps=steps,
        step_results={"LIFECYCLE": {"status": "FAILED"}},
        generated_at_utc=FIXED_TIME,
    )
    assert report["cycle_status"] == "FAILED"


def test_failed_dependency_blocks_later_step():
    steps = [
        {"step_name": "LIFECYCLE"},
        {"step_name": "INCOME", "dependencies": ["LIFECYCLE"]},
    ]
    report = build_enterprise_dividend_daily_cycle(
        steps=steps,
        step_results={"LIFECYCLE": {"status": "FAILED"}, "INCOME": {"status": "COMPLETED"}},
        generated_at_utc=FIXED_TIME,
    )
    assert report["steps"][1]["status"] == "BLOCKED"
    assert report["summary"]["blocked_steps"] == 1


def test_disabled_step_is_skipped():
    report = build_enterprise_dividend_daily_cycle(
        steps=[{"step_name": "LIFECYCLE", "enabled": False}],
        generated_at_utc=FIXED_TIME,
    )
    assert report["steps"][0]["status"] == "SKIPPED"
    assert report["cycle_status"] == "COMPLETED_WITH_WARNINGS"


def test_unknown_result_status_normalizes_to_completed():
    report = build_enterprise_dividend_daily_cycle(
        steps=[{"step_name": "LIFECYCLE"}],
        step_results={"LIFECYCLE": {"status": "SOMETHING_NEW"}},
        generated_at_utc=FIXED_TIME,
    )
    assert report["steps"][0]["status"] == "COMPLETED"


def test_governance_denies_execution_and_capital_movement():
    report = build_enterprise_dividend_daily_cycle(generated_at_utc=FIXED_TIME)
    assert report["governance"] == {
        "human_approval_required": True,
        "order_execution_allowed": False,
        "capital_movement_allowed": False,
        "policy_changes_allowed": False,
    }


def test_markdown_contains_ordered_steps_and_governance():
    report = build_enterprise_dividend_daily_cycle(generated_at_utc=FIXED_TIME)
    markdown = render_enterprise_dividend_daily_cycle_markdown(report)
    assert "# Enterprise Dividend Daily Cycle" in markdown
    assert "LIFECYCLE" in markdown
    assert "STRATEGY_HEALTH" in markdown
    assert "paper-only" in markdown


def test_write_outputs_json_and_markdown(tmp_path: Path):
    report = build_enterprise_dividend_daily_cycle(generated_at_utc=FIXED_TIME)
    paths = write_enterprise_dividend_daily_cycle(report, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()


def test_build_and_write_adds_output_files(tmp_path: Path):
    report = build_and_write_enterprise_dividend_daily_cycle(tmp_path, generated_at_utc=FIXED_TIME)
    assert set(report["output_files"]) == {"json", "markdown"}


def test_output_metadata_is_complete():
    report = build_enterprise_dividend_daily_cycle(generated_at_utc=FIXED_TIME)
    for key in (
        "module_name", "module_version", "schema_version", "cycle_id",
        "generated_at_utc", "paper_trade_mode", "cycle_status", "summary", "steps",
    ):
        assert key in report
