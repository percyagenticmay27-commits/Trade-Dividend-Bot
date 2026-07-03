"""
test_bot_capabilities.py

Pytest coverage for the read-only bot_capabilities module.

These tests verify the public API, JSON round-trip behavior, strict paper-only
validation, summary formatting, and static safety constraints. The tests do not
modify production code and do not call broker, Robinhood, subprocess, or order
execution paths.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import bot_capabilities as bc


REQUIRED_FIELDS = {
    "bot_name",
    "bot_type",
    "bot_version",
    "schema_version",
    "generated_at_utc",
    "generated_by",
    "module_name",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "capabilities",
    "supported_reports",
    "supported_outputs",
    "operational_scripts",
    "platform_integration_files",
    "safety_guarantees",
    "limitations",
}

REQUIRED_CAPABILITIES = {
    "paper_trading",
    "dividend_etf_management",
    "portfolio_snapshot_generation",
    "daily_paper_reporting",
    "weekly_portfolio_review",
    "strategy_health_reporting",
    "live_readiness_reporting",
    "email_report_delivery",
    "backup_support",
    "log_rotation_support",
    "health_check_support",
}

LIST_FIELDS = (
    "capabilities",
    "supported_reports",
    "supported_outputs",
    "operational_scripts",
    "platform_integration_files",
    "safety_guarantees",
    "limitations",
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


def _copy_payload() -> dict:
    """Return a fresh valid payload for mutation-based validation tests."""
    return bc.build_bot_capabilities()


def _module_source() -> str:
    """Return source text for the production module under test."""
    return Path(bc.__file__).read_text(encoding="utf-8")


def _module_ast() -> ast.Module:
    """Return parsed AST for the production module under test."""
    return ast.parse(_module_source())


def test_module_constants_are_expected() -> None:
    assert bc.MODULE_NAME == "bot_capabilities"
    assert bc.MODULE_VERSION == "1.0.0"
    assert bc.SCHEMA_VERSION == "1.0"
    assert bc.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_required_public_functions_exist_and_are_callable() -> None:
    assert callable(bc.build_bot_capabilities)
    assert callable(bc.validate_bot_capabilities)
    assert callable(bc.write_bot_capabilities)
    assert callable(bc.read_bot_capabilities)
    assert callable(bc.format_bot_capabilities_summary)


def test_build_bot_capabilities_returns_valid_profile() -> None:
    payload = bc.build_bot_capabilities()

    assert isinstance(payload, dict)
    assert REQUIRED_FIELDS.issubset(payload)
    assert bc.validate_bot_capabilities(payload) is True

    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False

    assert payload["module_name"] == bc.MODULE_NAME
    assert payload["bot_version"] == bc.MODULE_VERSION
    assert payload["schema_version"] == bc.SCHEMA_VERSION
    assert payload["generated_by"] == bc.GENERATED_BY


def test_capability_profile_structure_lists_are_valid() -> None:
    payload = bc.build_bot_capabilities()

    for field_name in LIST_FIELDS:
        assert isinstance(payload[field_name], list)
        assert payload[field_name], f"{field_name} should not be empty"
        assert all(isinstance(item, str) and item.strip() for item in payload[field_name])

    assert REQUIRED_CAPABILITIES.issubset(set(payload["capabilities"]))
    assert isinstance(payload["supported_reports"], list)
    assert isinstance(payload["supported_outputs"], list)
    assert isinstance(payload["operational_scripts"], list)
    assert isinstance(payload["safety_guarantees"], list)
    assert isinstance(payload["limitations"], list)


def test_validate_bot_capabilities_enforces_paper_only_flags() -> None:
    payload = _copy_payload()
    payload["paper_trade_mode"] = False
    with pytest.raises(ValueError, match="paper_trade_mode must be True"):
        bc.validate_bot_capabilities(payload)

    payload = _copy_payload()
    payload["live_trading_enabled"] = True
    with pytest.raises(ValueError, match="live_trading_enabled must be False"):
        bc.validate_bot_capabilities(payload)

    payload = _copy_payload()
    payload["broker_execution_enabled"] = True
    with pytest.raises(ValueError, match="broker_execution_enabled must be False"):
        bc.validate_bot_capabilities(payload)


def test_validate_bot_capabilities_rejects_missing_required_fields() -> None:
    for field_name in REQUIRED_FIELDS:
        payload = _copy_payload()
        payload.pop(field_name)
        with pytest.raises(ValueError, match="missing required capability keys"):
            bc.validate_bot_capabilities(payload)


def test_validate_bot_capabilities_rejects_malformed_payload_values() -> None:
    payload = _copy_payload()
    payload["capabilities"] = "paper_trading"
    with pytest.raises(ValueError, match="capabilities must be a list"):
        bc.validate_bot_capabilities(payload)

    payload = _copy_payload()
    payload["supported_reports"] = [""]
    with pytest.raises(ValueError, match="supported_reports\[0\]"):
        bc.validate_bot_capabilities(payload)

    payload = _copy_payload()
    payload["capabilities"] = ["paper_trading", "live_trading"]
    with pytest.raises(ValueError, match="forbidden live-trading capabilities"):
        bc.validate_bot_capabilities(payload)


def test_validate_bot_capabilities_rejects_incorrect_metadata() -> None:
    metadata_cases = (
        ("module_name", "wrong_module", "module_name"),
        ("bot_version", "999.0.0", "bot_version"),
        ("schema_version", "999.0", "schema_version"),
        ("generated_by", "unknown", "generated_by"),
    )

    for field_name, bad_value, expected_message in metadata_cases:
        payload = _copy_payload()
        payload[field_name] = bad_value
        with pytest.raises(ValueError, match=expected_message):
            bc.validate_bot_capabilities(payload)


def test_write_and_read_bot_capabilities_round_trip(tmp_path: Path) -> None:
    output_path = tmp_path / "bot_capabilities.json"

    written_payload = bc.write_bot_capabilities(path=str(output_path))
    read_payload = bc.read_bot_capabilities(path=str(output_path))

    assert output_path.exists()
    assert read_payload == written_payload
    assert bc.validate_bot_capabilities(read_payload) is True
    assert read_payload["paper_trade_mode"] is True
    assert read_payload["live_trading_enabled"] is False
    assert read_payload["broker_execution_enabled"] is False


def test_format_bot_capabilities_summary_contains_key_sections() -> None:
    payload = bc.build_bot_capabilities()
    summary = bc.format_bot_capabilities_summary(payload)

    assert isinstance(summary, str)
    assert summary.endswith("\n")
    assert payload["bot_name"] in summary
    assert "# Agentic Robin Dividend Bot Capabilities" in summary
    assert "## Capabilities" in summary
    assert "## Supported Reports" in summary
    assert "## Supported Outputs" in summary
    assert "## Operational Scripts" in summary
    assert "## Platform Integration Files" in summary
    assert "## Safety Guarantees" in summary
    assert "## Limitations" in summary
    assert "Paper trade mode: True" in summary
    assert "Live trading enabled: False" in summary
    assert "Broker execution enabled: False" in summary


def test_format_bot_capabilities_summary_validates_payload_first() -> None:
    payload = _copy_payload()
    payload["broker_execution_enabled"] = True

    with pytest.raises(ValueError, match="broker_execution_enabled must be False"):
        bc.format_bot_capabilities_summary(payload)


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


def test_static_safety_no_mutation_of_runtime_workflow_files() -> None:
    source = _module_source()

    forbidden_write_targets = (
        "run_daily_paper_cycle.py",
        "send_daily_reports.py",
        "paper_state.json",
        "paper_trade_log.csv",
        "portfolio_snapshot.csv",
    )
    suspicious_write_patterns = (
        ".write_text(",
        "open(",
    )

    for target in forbidden_write_targets:
        assert target not in source or "does not modify" in source.lower() or target.endswith((".json", ".csv"))

    assert "subprocess" not in source.lower()
    assert "os.system" not in source.lower()
    assert "bot_capabilities.json" in source
    assert any(pattern in source for pattern in suspicious_write_patterns)
