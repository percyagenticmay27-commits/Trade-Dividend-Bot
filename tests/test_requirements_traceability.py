from pathlib import Path

import pytest

from src.dividend_bot.platform_foundation import PlatformValidationError
from src.dividend_bot.requirements_traceability import (
    TraceabilityCheck,
    build_traceability_summary,
    require_traceability,
    validate_traceability,
)


def test_custom_traceability_check_passes(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "rule.md"
    target.parent.mkdir(parents=True)
    target.write_text("Status: FROZEN\nGovernance\n", encoding="utf-8")

    results = validate_traceability(
        tmp_path,
        checks=(TraceabilityCheck("rule", "docs/rule.md", ("FROZEN", "Governance")),),
    )

    assert len(results) == 1
    assert results[0].passed is True


def test_missing_file_is_reported(tmp_path: Path) -> None:
    results = validate_traceability(
        tmp_path,
        checks=(TraceabilityCheck("missing", "missing.md"),),
    )

    assert results[0].passed is False
    assert results[0].message == "required file is missing"


def test_missing_marker_is_reported(tmp_path: Path) -> None:
    target = tmp_path / "file.md"
    target.write_text("Status: ACTIVE\n", encoding="utf-8")

    results = validate_traceability(
        tmp_path,
        checks=(TraceabilityCheck("marker", "file.md", ("FROZEN",)),),
    )

    assert results[0].passed is False
    assert "FROZEN" in results[0].message


def test_require_traceability_raises_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(PlatformValidationError, match="requirements traceability failed"):
        require_traceability()


def test_summary_reports_pass_and_fail_counts() -> None:
    results = (
        type("Result", (), {"name": "a", "path": "a", "passed": True, "message": "ok"})(),
        type("Result", (), {"name": "b", "path": "b", "passed": False, "message": "bad"})(),
    )

    summary = build_traceability_summary(results)

    assert summary["status"] == "FAIL"
    assert summary["total_checks"] == 2
    assert summary["passed_checks"] == 1
    assert summary["failed_checks"] == 1
    assert summary["failures"][0]["name"] == "b"


def test_repository_traceability_currently_passes() -> None:
    results = require_traceability(Path("."))
    summary = build_traceability_summary(results)

    assert summary["status"] == "PASS"
    assert summary["failed_checks"] == 0
