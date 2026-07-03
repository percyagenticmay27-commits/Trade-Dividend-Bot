"""
test_bot_environment_check.py

Pytest coverage for the read-only bot_environment_check module.

These tests verify the public API, JSON round-trip behavior, strict paper-only
validation, environment status handling, summary formatting, and static safety
constraints. The tests do not modify production code and do not call broker,
Robinhood, subprocess, operating-system command, or order execution paths.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import bot_environment_check as bec


REQUIRED_FIELDS = {
    "bot_name",
    "bot_type",
    "bot_version",
    "schema_version",
    "generated_at_utc",
    "generated_by",
    "module_name",
    "module_version",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "python_version",
    "platform",
    "working_directory",
    "required_files",
    "missing_required_files",
    "optional_files",
    "missing_optional_files",
    "required_directories",
    "missing_required_directories",
    "environment_status",
    "warnings",
    "errors",
    "safety_guarantees",
}

LIST_FIELDS = (
    "required_files",
    "missing_required_files",
    "optional_files",
    "missing_optional_files",
    "required_directories",
    "missing_required_directories",
    "warnings",
    "errors",
    "safety_guarantees",
)

NON_EMPTY_LIST_FIELDS = (
    "required_files",
    "optional_files",
    "required_directories",
    "safety_guarantees",
)

BROKER_IMPORT_FRAGMENTS = (
    "robinhood",
    "robin_stocks",
    "alpaca",
    "ib_insync",
    "interactivebrokers",
    "tdameritrade",
    "schwab",
    "etrade",
    "binance",
    "coinbase",
    "ccxt",
)

TRADING_LOGIC_CALL_NAMES = {
    "buy",
    "sell",
    "trade",
    "execute_trade",
    "execute_order",
    "place_order",
    "place_buy_order",
    "place_sell_order",
    "submit_order",
    "market_buy",
    "market_sell",
    "limit_buy",
    "limit_sell",
}


def _module_source() -> str:
    """Return source text for the production module under test."""
    return Path(bec.__file__).read_text(encoding="utf-8")


def _module_ast() -> ast.Module:
    """Return parsed AST for the production module under test."""
    return ast.parse(_module_source())


def _create_required_files(root: Path) -> None:
    """Create the required project files in a temporary root."""
    for filename in bec.REQUIRED_FILES:
        (root / filename).write_text(f"placeholder for {filename}\n", encoding="utf-8")


def _create_optional_files(root: Path) -> None:
    """Create the optional project files in a temporary root."""
    for filename in bec.OPTIONAL_FILES:
        (root / filename).write_text(f"placeholder for {filename}\n", encoding="utf-8")


def _valid_payload(tmp_path: Path) -> dict:
    _create_required_files(tmp_path)
    _create_optional_files(tmp_path)
    return bec.build_bot_environment_check(root_path=tmp_path)


def test_module_constants_are_expected() -> None:
    assert bec.MODULE_NAME == "bot_environment_check"
    assert bec.MODULE_VERSION == "1.0.0"
    assert bec.SCHEMA_VERSION == "1.0"
    assert bec.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_required_public_functions_exist_and_are_callable() -> None:
    assert callable(bec.build_bot_environment_check)
    assert callable(bec.validate_bot_environment_check)
    assert callable(bec.write_bot_environment_check)
    assert callable(bec.read_bot_environment_check)
    assert callable(bec.format_bot_environment_check_summary)


def test_build_bot_environment_check_returns_valid_ok_payload(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)

    assert isinstance(payload, dict)
    assert REQUIRED_FIELDS.issubset(payload)
    assert bec.validate_bot_environment_check(payload) is True

    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["environment_status"] == "OK"
    assert payload["missing_required_files"] == []
    assert payload["missing_optional_files"] == []
    assert payload["errors"] == []

    assert payload["module_name"] == bec.MODULE_NAME
    assert payload["module_version"] == bec.MODULE_VERSION
    assert payload["bot_version"] == bec.MODULE_VERSION
    assert payload["schema_version"] == bec.SCHEMA_VERSION
    assert payload["generated_by"] == bec.GENERATED_BY


def test_environment_check_list_fields_are_valid(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)

    for field_name in LIST_FIELDS:
        assert isinstance(payload[field_name], list)
        assert all(isinstance(item, str) and item.strip() for item in payload[field_name])

    for field_name in NON_EMPTY_LIST_FIELDS:
        assert payload[field_name], f"{field_name} should not be empty"


def test_validate_bot_environment_check_enforces_paper_only_flags(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["paper_trade_mode"] = False
    with pytest.raises(ValueError, match="paper_trade_mode"):
        bec.validate_bot_environment_check(payload)

    payload = _valid_payload(tmp_path)
    payload["live_trading_enabled"] = True
    with pytest.raises(ValueError, match="live_trading_enabled"):
        bec.validate_bot_environment_check(payload)

    payload = _valid_payload(tmp_path)
    payload["broker_execution_enabled"] = True
    with pytest.raises(ValueError, match="broker_execution_enabled"):
        bec.validate_bot_environment_check(payload)


def test_validate_bot_environment_check_rejects_missing_required_fields(tmp_path: Path) -> None:
    for field_name in REQUIRED_FIELDS:
        payload = _valid_payload(tmp_path)
        payload.pop(field_name)
        with pytest.raises(ValueError, match="Missing required fields"):
            bec.validate_bot_environment_check(payload)


def test_validate_bot_environment_check_rejects_malformed_payload_values(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["required_files"] = "run_daily_paper_cycle.py"
    with pytest.raises(ValueError, match="required_files must be a list"):
        bec.validate_bot_environment_check(payload)

    payload = _valid_payload(tmp_path)
    payload["optional_files"] = [""]
    with pytest.raises(ValueError, match=r"optional_files\[0\]"):
        bec.validate_bot_environment_check(payload)

    payload = _valid_payload(tmp_path)
    payload["safety_guarantees"] = []
    with pytest.raises(ValueError, match="safety_guarantees must not be empty"):
        bec.validate_bot_environment_check(payload)

    payload = _valid_payload(tmp_path)
    payload["environment_status"] = "BROKEN"
    with pytest.raises(ValueError, match="environment_status"):
        bec.validate_bot_environment_check(payload)

    with pytest.raises(ValueError, match="mapping"):
        bec.validate_bot_environment_check(["not", "a", "dict"])


def test_validate_bot_environment_check_rejects_incorrect_metadata(tmp_path: Path) -> None:
    metadata_cases = (
        ("module_name", "wrong_module", "module_name"),
        ("module_version", "999.0.0", "module_version"),
        ("bot_version", "999.0.0", "bot_version"),
        ("schema_version", "999.0", "schema_version"),
        ("generated_by", "unknown", "generated_by"),
    )

    for field_name, bad_value, expected_message in metadata_cases:
        payload = _valid_payload(tmp_path)
        payload[field_name] = bad_value
        with pytest.raises(ValueError, match=expected_message):
            bec.validate_bot_environment_check(payload)


def test_missing_required_files_produce_error(tmp_path: Path) -> None:
    _create_optional_files(tmp_path)

    payload = bec.build_bot_environment_check(root_path=tmp_path)

    assert payload["environment_status"] == "ERROR"
    assert payload["missing_required_files"]
    assert payload["errors"]
    assert bec.validate_bot_environment_check(payload) is True


def test_missing_optional_files_produce_warning_only(tmp_path: Path) -> None:
    _create_required_files(tmp_path)

    payload = bec.build_bot_environment_check(root_path=tmp_path)

    assert payload["environment_status"] == "WARNING"
    assert payload["missing_required_files"] == []
    assert payload["missing_optional_files"]
    assert payload["errors"] == []
    assert payload["warnings"]
    assert bec.validate_bot_environment_check(payload) is True


def test_environment_status_consistency_is_enforced(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["environment_status"] = "WARNING"
    with pytest.raises(ValueError, match="OK"):
        bec.validate_bot_environment_check(payload)

    payload = _valid_payload(tmp_path)
    payload["missing_required_files"] = ["run_daily_paper_cycle.py"]
    payload["environment_status"] = "WARNING"
    payload["errors"] = ["Missing required files: run_daily_paper_cycle.py"]
    with pytest.raises(ValueError, match="ERROR"):
        bec.validate_bot_environment_check(payload)

    payload = _valid_payload(tmp_path)
    payload["missing_optional_files"] = ["run_dividend_bot.sh"]
    payload["environment_status"] = "OK"
    payload["warnings"] = ["Missing optional files: run_dividend_bot.sh"]
    with pytest.raises(ValueError, match="WARNING"):
        bec.validate_bot_environment_check(payload)


def test_write_and_read_bot_environment_check_round_trip(tmp_path: Path) -> None:
    root_path = tmp_path / "project"
    root_path.mkdir()
    _create_required_files(root_path)
    output_path = tmp_path / "bot_environment_check.json"

    written_payload = bec.write_bot_environment_check(path=output_path, root_path=root_path)
    read_payload = bec.read_bot_environment_check(path=output_path)

    assert output_path.exists()
    assert read_payload == written_payload
    assert bec.validate_bot_environment_check(read_payload) is True
    assert read_payload["paper_trade_mode"] is True
    assert read_payload["live_trading_enabled"] is False
    assert read_payload["broker_execution_enabled"] is False
    assert read_payload["environment_status"] == "WARNING"


def test_format_bot_environment_check_summary_contains_key_sections(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    summary = bec.format_bot_environment_check_summary(payload)

    assert isinstance(summary, str)
    assert summary.endswith("\n")
    assert payload["bot_name"] in summary
    assert "# Agentic Robin Dividend Bot Environment Check" in summary
    assert "## Paper-Only Safety" in summary
    assert "## Runtime Environment" in summary
    assert "## Required Files" in summary
    assert "## Missing Required Files" in summary
    assert "## Optional Files" in summary
    assert "## Missing Optional Files" in summary
    assert "## Required Directories" in summary
    assert "## Missing Required Directories" in summary
    assert "## Warnings" in summary
    assert "## Errors" in summary
    assert "## Safety Guarantees" in summary
    assert "paper_trade_mode: True" in summary
    assert "live_trading_enabled: False" in summary
    assert "broker_execution_enabled: False" in summary


def test_format_bot_environment_check_summary_validates_payload_first(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["broker_execution_enabled"] = True

    with pytest.raises(ValueError, match="broker_execution_enabled"):
        bec.format_bot_environment_check_summary(payload)


def test_static_safety_no_broker_or_robinhood_imports() -> None:
    tree = _module_ast()
    imported_modules = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.append((node.module or "").lower())

    assert imported_modules
    for imported_module in imported_modules:
        assert not any(fragment in imported_module for fragment in BROKER_IMPORT_FRAGMENTS)


def test_static_safety_no_subprocess_or_os_system_usage() -> None:
    tree = _module_ast()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imported_names = []
            if isinstance(node, ast.Import):
                imported_names = [alias.name for alias in node.names]
            else:
                imported_names = [node.module or ""] + [alias.name for alias in node.names]
            assert "subprocess" not in {name.lower() for name in imported_names}

        if isinstance(node, ast.Call):
            function = node.func
            assert not (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "os"
                and function.attr == "system"
            )

    source = _module_source().lower()
    assert "subprocess" not in source
    assert "os.system" not in source


def test_static_safety_no_real_order_placement_logic() -> None:
    tree = _module_ast()

    function_names = {
        node.name.lower()
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    call_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id.lower())
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr.lower())

    assert function_names.isdisjoint(TRADING_LOGIC_CALL_NAMES)
    assert call_names.isdisjoint(TRADING_LOGIC_CALL_NAMES)


def test_static_safety_does_not_modify_runtime_workflow_files() -> None:
    source = _module_source()

    assert "run_daily_paper_cycle.py" in source
    assert "send_daily_reports.py" in source
    assert "bot_environment_check.json" in source
    assert "connect_to_robinhood" not in source.lower()
    assert "place_order" not in source.lower()
    assert "submit_order" not in source.lower()
    assert "execute_order" not in source.lower()
