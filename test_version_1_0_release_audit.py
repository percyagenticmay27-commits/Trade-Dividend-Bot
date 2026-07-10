"""Tests for version_1_0_release_audit.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import version_1_0_release_audit as audit


def _write(path: Path, text: str = "VALUE = 1\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _complete_project(root: Path) -> None:
    for name in audit.REQUIRED_STAGE_MODULES + audit.REQUIRED_CONTROL_FILES:
        _write(root / name)
        _write(root / f"test_{Path(name).stem}.py", "def test_placeholder():\n    assert True\n")


def test_public_functions_exist():
    for name in [
        "discover_python_files",
        "compile_source_files",
        "scan_safety",
        "build_version_1_0_release_audit",
        "validate_version_1_0_release_audit",
        "format_version_1_0_release_audit_markdown",
        "write_version_1_0_release_audit",
    ]:
        assert callable(getattr(audit, name))


def test_complete_minimal_project_passes(tmp_path):
    _complete_project(tmp_path)
    payload = audit.build_version_1_0_release_audit(str(tmp_path))
    assert payload["audit_status"] == "PASS"
    assert payload["present_required_stage_count"] == 17
    assert payload["missing_required_stage_modules"] == []
    assert payload["missing_control_files"] == []
    assert payload["compile_errors"] == []
    assert payload["safety_findings"] == []


def test_missing_required_stage_fails(tmp_path):
    _complete_project(tmp_path)
    (tmp_path / audit.REQUIRED_STAGE_MODULES[0]).unlink()
    payload = audit.build_version_1_0_release_audit(str(tmp_path))
    assert payload["audit_status"] == "FAIL"
    assert audit.REQUIRED_STAGE_MODULES[0] in payload["missing_required_stage_modules"]


def test_compile_error_fails(tmp_path):
    _complete_project(tmp_path)
    _write(tmp_path / "broken.py", "def broken(:\n")
    payload = audit.build_version_1_0_release_audit(str(tmp_path))
    assert payload["audit_status"] == "FAIL"
    assert any(item["path"] == "broken.py" for item in payload["compile_errors"])


def test_ast_safety_detects_forbidden_import_and_call(tmp_path):
    _complete_project(tmp_path)
    _write(
        tmp_path / "unsafe.py",
        "import subprocess\n"
        "def run():\n"
        "    subprocess.run(['echo', 'x'])\n",
    )
    payload = audit.build_version_1_0_release_audit(str(tmp_path))
    names = {item["name"] for item in payload["safety_findings"]}
    assert "subprocess" in names
    assert "subprocess.run" in names
    assert payload["audit_status"] == "FAIL"


def test_missing_matching_test_is_warning(tmp_path):
    _complete_project(tmp_path)
    _write(tmp_path / "extra_module.py")
    payload = audit.build_version_1_0_release_audit(str(tmp_path))
    assert payload["audit_status"] == "WARNING"
    assert "extra_module.py" in payload["production_modules_without_matching_tests"]


def test_validate_rejects_wrong_safety_flags(tmp_path):
    _complete_project(tmp_path)
    payload = audit.build_version_1_0_release_audit(str(tmp_path))
    for field, value in [
        ("paper_trade_mode", False),
        ("reporting_only", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            audit.validate_version_1_0_release_audit(bad)


def test_write_json_and_markdown(tmp_path):
    _complete_project(tmp_path)
    payload = audit.write_version_1_0_release_audit(str(tmp_path))
    json_path = tmp_path / "version_1_0_release_audit.json"
    markdown_path = tmp_path / "version_1_0_release_audit.md"
    assert json_path.exists()
    assert markdown_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8")) == payload
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Dividend Bot Version 1.0 Release Audit" in markdown
    assert "Required Stages Present: 17/17" in markdown
