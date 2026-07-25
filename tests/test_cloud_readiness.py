import json
from pathlib import Path

from src.dividend_bot.cloud_readiness import (
    BROKER_EXECUTION_ENABLED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    build_cloud_readiness_report,
    build_health_check,
    ensure_runtime_directories,
    scheduler_command,
    validate_environment,
    write_health_check,
    write_structured_log,
)

FIXED_TIME = "2026-07-25T18:00:00Z"


def test_safety_constants_are_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False


def test_environment_ready_when_required_value_exists():
    report = validate_environment({"DIVIDEND_BOT_ENV": "paper"})
    assert report["status"] == "READY"
    assert report["missing_required"] == []


def test_environment_not_ready_when_required_value_missing():
    report = validate_environment({})
    assert report["status"] == "NOT_READY"
    assert report["missing_required"] == ["DIVIDEND_BOT_ENV"]


def test_optional_environment_is_reported():
    report = validate_environment({"DIVIDEND_BOT_ENV": "paper", "DIVIDEND_BOT_TIMEZONE": "America/Chicago"})
    assert report["configured_optional"] == ["DIVIDEND_BOT_TIMEZONE"]


def test_runtime_directories_are_created(tmp_path: Path):
    paths = ensure_runtime_directories(tmp_path)
    assert set(paths) == {"results", "logs", "state", "runtime"}
    assert all(Path(path).is_dir() for path in paths.values())


def test_custom_runtime_directories_are_supported(tmp_path: Path):
    paths = ensure_runtime_directories(tmp_path, ["a", "b"])
    assert set(paths) == {"a", "b"}


def test_structured_log_is_json_lines(tmp_path: Path):
    path = tmp_path / "logs" / "runtime.jsonl"
    record = write_structured_log(path, level="info", event="startup", message="ready", timestamp_utc=FIXED_TIME)
    stored = json.loads(path.read_text(encoding="utf-8").strip())
    assert stored == record
    assert stored["level"] == "INFO"
    assert stored["paper_trade_mode"] is True


def test_structured_log_appends(tmp_path: Path):
    path = tmp_path / "runtime.jsonl"
    write_structured_log(path, level="info", event="one", message="1", timestamp_utc=FIXED_TIME)
    write_structured_log(path, level="warning", event="two", message="2", timestamp_utc=FIXED_TIME)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_health_check_is_healthy_when_requirements_exist(tmp_path: Path):
    required = tmp_path / "required.json"
    required.write_text("{}", encoding="utf-8")
    directories = ensure_runtime_directories(tmp_path)
    report = build_health_check(
        environment_report=validate_environment({"DIVIDEND_BOT_ENV": "paper"}),
        runtime_directories=directories,
        required_files=[required],
        generated_at_utc=FIXED_TIME,
    )
    assert report["status"] == "HEALTHY"
    assert report["missing_required_files"] == []


def test_health_check_degraded_for_missing_file(tmp_path: Path):
    report = build_health_check(
        environment_report=validate_environment({"DIVIDEND_BOT_ENV": "paper"}),
        runtime_directories=ensure_runtime_directories(tmp_path),
        required_files=[tmp_path / "missing.json"],
        generated_at_utc=FIXED_TIME,
    )
    assert report["status"] == "DEGRADED"


def test_health_check_degraded_for_environment_failure(tmp_path: Path):
    report = build_health_check(
        environment_report=validate_environment({}),
        runtime_directories=ensure_runtime_directories(tmp_path),
        generated_at_utc=FIXED_TIME,
    )
    assert report["status"] == "DEGRADED"


def test_health_governance_denies_execution(tmp_path: Path):
    report = build_cloud_readiness_report(tmp_path, environment={"DIVIDEND_BOT_ENV": "paper"}, generated_at_utc=FIXED_TIME)
    assert report["governance"] == {
        "order_execution_allowed": False,
        "brokerage_communication_allowed": False,
        "capital_movement_allowed": False,
    }


def test_write_health_check_creates_json(tmp_path: Path):
    report = build_cloud_readiness_report(tmp_path, environment={"DIVIDEND_BOT_ENV": "paper"}, generated_at_utc=FIXED_TIME)
    destination = write_health_check(report, tmp_path / "results" / "health.json")
    loaded = json.loads(Path(destination).read_text(encoding="utf-8"))
    assert loaded["status"] == "HEALTHY"


def test_scheduler_command_targets_paper_cycle(tmp_path: Path):
    command = scheduler_command(tmp_path)
    assert command[1].endswith("run_daily_paper_cycle.py")


def test_fixed_timestamp_is_preserved(tmp_path: Path):
    report = build_cloud_readiness_report(tmp_path, environment={"DIVIDEND_BOT_ENV": "paper"}, generated_at_utc=FIXED_TIME)
    assert report["generated_at_utc"] == FIXED_TIME


def test_output_metadata_is_complete(tmp_path: Path):
    report = build_cloud_readiness_report(tmp_path, environment={"DIVIDEND_BOT_ENV": "paper"}, generated_at_utc=FIXED_TIME)
    for key in ("module_name", "module_version", "schema_version", "status", "python", "runtime_directories"):
        assert key in report
