"""Tests for the read-only Dividend Bot report integrity module."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import bot_report_integrity as integrity


REQUIRED_REPORTS = [
    "daily_paper_report.md",
    "daily_change_summary.md",
    "portfolio_snapshot.csv",
    "paper_trade_log.csv",
    "paper_state.json",
]

OPTIONAL_REPORTS = [
    "strategy_health_report.md",
    "live_readiness_report.md",
    "weekly_portfolio_review.md",
    "performance_summary.md",
    "walk_forward_summary.md",
    "performance_report.csv",
    "strategy_health.csv",
    "pair_health.csv",
    "live_readiness.csv",
    "email_delivery_log.csv",
    "snapshot_manifest.json",
    "bot_capabilities.json",
    "bot_environment_check.json",
]

REQUIRED_FIELDS = [
    "module_name",
    "generated_by",
    "bot_name",
    "bot_type",
    "bot_version",
    "schema_version",
    "generated_at_utc",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "required_reports",
    "missing_required_reports",
    "unreadable_required_reports",
    "optional_reports",
    "missing_optional_reports",
    "report_file_details",
    "integrity_status",
    "warnings",
    "errors",
    "safety_guarantees",
]

LIST_FIELDS = [
    "required_reports",
    "missing_required_reports",
    "unreadable_required_reports",
    "optional_reports",
    "missing_optional_reports",
    "warnings",
    "errors",
    "safety_guarantees",
]


def _create_reports(root: Path, names: list[str]) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"test content for {name}\n", encoding="utf-8")


def _complete_report_root(tmp_path: Path) -> Path:
    root = tmp_path / "complete_reports"
    root.mkdir()
    _create_reports(root, REQUIRED_REPORTS + OPTIONAL_REPORTS)
    return root


def _valid_payload(tmp_path: Path) -> dict:
    root = _complete_report_root(tmp_path)
    return integrity.build_bot_report_integrity(root_path=root)


def _source_text() -> str:
    return Path(integrity.__file__).read_text(encoding="utf-8")


def test_module_constants_are_expected() -> None:
    assert integrity.MODULE_NAME == "bot_report_integrity"
    assert integrity.MODULE_VERSION == "1.0.0"
    assert integrity.SCHEMA_VERSION == "1.0"
    assert integrity.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_required_public_functions_exist_and_are_callable() -> None:
    for function_name in [
        "build_bot_report_integrity",
        "validate_bot_report_integrity",
        "write_bot_report_integrity",
        "read_bot_report_integrity",
        "format_bot_report_integrity_summary",
    ]:
        assert hasattr(integrity, function_name)
        assert callable(getattr(integrity, function_name))


def test_build_bot_report_integrity_returns_valid_ok_payload(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)

    assert integrity.validate_bot_report_integrity(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["integrity_status"] == "OK"
    assert payload["missing_required_reports"] == []
    assert payload["unreadable_required_reports"] == []
    assert payload["missing_optional_reports"] == []

    for field in REQUIRED_FIELDS:
        assert field in payload


def test_report_integrity_list_fields_are_valid(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)

    for field in LIST_FIELDS:
        assert isinstance(payload[field], list)
        for entry in payload[field]:
            assert isinstance(entry, str)
            assert entry.strip()

    assert payload["required_reports"] == REQUIRED_REPORTS
    assert payload["optional_reports"] == OPTIONAL_REPORTS
    assert payload["required_reports"]
    assert payload["optional_reports"]
    assert payload["safety_guarantees"]


def test_report_file_details_structure_is_valid(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    details = payload["report_file_details"]

    assert isinstance(details, list)
    assert [item["path"] for item in details] == REQUIRED_REPORTS + OPTIONAL_REPORTS

    for item in details:
        assert set(item) == {
            "path",
            "required",
            "exists",
            "readable",
            "size_bytes",
            "modified_at_utc",
        }
        assert isinstance(item["path"], str)
        assert item["path"].strip()
        assert isinstance(item["required"], bool)
        assert isinstance(item["exists"], bool)
        assert isinstance(item["readable"], bool)
        assert item["size_bytes"] is None or isinstance(item["size_bytes"], int)
        assert item["modified_at_utc"] is None or isinstance(item["modified_at_utc"], str)


def test_validate_bot_report_integrity_enforces_paper_only_flags(tmp_path: Path) -> None:
    base = _valid_payload(tmp_path)

    for field, bad_value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
    ]:
        payload = dict(base)
        payload[field] = bad_value
        with pytest.raises(ValueError):
            integrity.validate_bot_report_integrity(payload)


def test_validate_bot_report_integrity_rejects_missing_required_fields(tmp_path: Path) -> None:
    base = _valid_payload(tmp_path)

    for field in REQUIRED_FIELDS:
        payload = dict(base)
        payload.pop(field)
        with pytest.raises(ValueError):
            integrity.validate_bot_report_integrity(payload)


def test_validate_bot_report_integrity_rejects_malformed_payload_values(tmp_path: Path) -> None:
    base = _valid_payload(tmp_path)

    malformed_cases = [
        ("required_reports", []),
        ("optional_reports", []),
        ("safety_guarantees", []),
        ("missing_required_reports", "daily_paper_report.md"),
        ("unreadable_required_reports", "paper_state.json"),
        ("missing_optional_reports", "strategy_health_report.md"),
        ("warnings", "warning"),
        ("errors", "error"),
        ("required_reports", [""]),
        ("optional_reports", ["   "]),
        ("safety_guarantees", [None]),
        ("integrity_status", "BAD"),
        ("report_file_details", "not-a-list"),
    ]

    for field, bad_value in malformed_cases:
        payload = dict(base)
        payload[field] = bad_value
        with pytest.raises(ValueError):
            integrity.validate_bot_report_integrity(payload)

    with pytest.raises(ValueError):
        integrity.validate_bot_report_integrity("not-a-mapping")  # type: ignore[arg-type]


def test_validate_bot_report_integrity_rejects_incorrect_metadata(tmp_path: Path) -> None:
    base = _valid_payload(tmp_path)

    for field, bad_value in [
        ("module_name", "wrong_module"),
        ("generated_by", "wrong_generator"),
        ("bot_name", "Wrong Bot"),
        ("bot_type", "wrong_type"),
        ("bot_version", "9.9.9"),
        ("schema_version", "9.9"),
    ]:
        payload = dict(base)
        payload[field] = bad_value
        with pytest.raises(ValueError):
            integrity.validate_bot_report_integrity(payload)


def test_integrity_status_must_be_ok_warning_or_error(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    assert payload["integrity_status"] in {"OK", "WARNING", "ERROR"}

    payload["integrity_status"] = "UNKNOWN"
    with pytest.raises(ValueError):
        integrity.validate_bot_report_integrity(payload)


def test_missing_required_reports_produce_error(tmp_path: Path) -> None:
    root = tmp_path / "missing_required"
    root.mkdir()
    _create_reports(root, OPTIONAL_REPORTS)

    payload = integrity.build_bot_report_integrity(root_path=root)

    assert payload["integrity_status"] == "ERROR"
    assert payload["missing_required_reports"] == REQUIRED_REPORTS
    assert payload["errors"]
    assert integrity.validate_bot_report_integrity(payload) is True


def test_missing_optional_reports_produce_warning_only(tmp_path: Path) -> None:
    root = tmp_path / "missing_optional"
    root.mkdir()
    _create_reports(root, REQUIRED_REPORTS)

    payload = integrity.build_bot_report_integrity(root_path=root)

    assert payload["integrity_status"] == "WARNING"
    assert payload["missing_required_reports"] == []
    assert payload["unreadable_required_reports"] == []
    assert payload["missing_optional_reports"] == OPTIONAL_REPORTS
    assert payload["warnings"]
    assert payload["errors"] == []
    assert integrity.validate_bot_report_integrity(payload) is True


def test_unreadable_required_reports_produce_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _complete_report_root(tmp_path)
    unreadable_name = "paper_state.json"
    original_is_readable = integrity._is_readable_file

    def fake_is_readable(path: Path) -> bool:
        if path.name == unreadable_name:
            return False
        return original_is_readable(path)

    monkeypatch.setattr(integrity, "_is_readable_file", fake_is_readable)
    payload = integrity.build_bot_report_integrity(root_path=root)

    assert payload["integrity_status"] == "ERROR"
    assert payload["missing_required_reports"] == []
    assert payload["unreadable_required_reports"] == [unreadable_name]
    assert payload["errors"]
    assert integrity.validate_bot_report_integrity(payload) is True


def test_integrity_status_consistency_is_enforced(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)

    payload["missing_required_reports"] = ["paper_state.json"]
    payload["integrity_status"] = "WARNING"
    with pytest.raises(ValueError):
        integrity.validate_bot_report_integrity(payload)

    payload = _valid_payload(tmp_path)
    payload["missing_optional_reports"] = ["strategy_health_report.md"]
    payload["integrity_status"] = "OK"
    with pytest.raises(ValueError):
        integrity.validate_bot_report_integrity(payload)


def test_write_and_read_bot_report_integrity_round_trip(tmp_path: Path) -> None:
    root = _complete_report_root(tmp_path)
    output_path = tmp_path / "bot_report_integrity.json"

    written = integrity.write_bot_report_integrity(path=output_path, root_path=root)
    read_back = integrity.read_bot_report_integrity(path=output_path)

    assert output_path.exists()
    assert read_back == written
    assert integrity.validate_bot_report_integrity(read_back) is True


def test_format_bot_report_integrity_summary_contains_key_sections(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    summary = integrity.format_bot_report_integrity_summary(payload)

    expected_sections = [
        "# Bot Report Integrity Summary",
        "## Safety Flags",
        "## Required Reports",
        "## Missing Required Reports",
        "## Unreadable Required Reports",
        "## Optional Reports",
        "## Missing Optional Reports",
        "## Report File Details",
        "## Warnings",
        "## Errors",
        "## Safety Guarantees",
    ]
    for section in expected_sections:
        assert section in summary

    assert "Integrity Status: OK" in summary
    assert "daily_paper_report.md" in summary
    assert "paper_state.json" in summary


def test_format_bot_report_integrity_summary_validates_payload_first(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["paper_trade_mode"] = False

    with pytest.raises(ValueError):
        integrity.format_bot_report_integrity_summary(payload)


def test_static_safety_no_broker_or_robinhood_imports() -> None:
    source = _source_text().lower()

    forbidden_patterns = [
        "import robinhood",
        "from robinhood",
        "robin_stocks",
        "import alpaca",
        "from alpaca",
        "import ibapi",
        "from ibapi",
        "broker_api",
        "brokerclient",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in source


def test_static_safety_no_subprocess_or_os_system_usage() -> None:
    source = _source_text().lower()

    forbidden_patterns = [
        "import subprocess",
        "from subprocess",
        "subprocess.",
        "popen(",
        "from subprocess import run",
        "os.system(",
        ".system(",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in source


def test_static_safety_no_real_order_placement_logic() -> None:
    source = _source_text().lower()

    forbidden_patterns = [
        "place_order(",
        "submit_order(",
        "create_order(",
        "market_order(",
        "limit_order(",
        "buy_order(",
        "sell_order(",
        "order_buy",
        "order_sell",
        "execute_trade(",
        "execute_order(",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in source


def test_static_safety_does_not_modify_runtime_workflow_files() -> None:
    source = _source_text()

    assert "run_daily_paper_cycle.py" not in source or "write_text" not in source
    assert "send_daily_reports.py" not in source or "write_text" not in source
    assert "run_daily_paper_cycle" not in source.lower()
    assert "send_daily_reports" not in source.lower()


def test_module_import_is_side_effect_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    importlib.reload(integrity)
    after = set(tmp_path.iterdir())

    assert after == before
