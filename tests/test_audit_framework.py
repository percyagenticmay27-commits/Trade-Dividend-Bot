from datetime import datetime, timezone

import pytest

from src.dividend_bot.audit_framework import (
    AuditCheckResult,
    AuditModel,
    AuditRenderer,
    ensure_single_audit_scope,
    evaluate_release_gate,
)
from src.dividend_bot.platform_entities import FindingStatus
from src.dividend_bot.platform_foundation import PlatformValidationError

NOW = datetime(2026, 7, 29, tzinfo=timezone.utc)


def strategy_model(status=FindingStatus.PASS):
    return AuditModel(
        scope_type="STRATEGY",
        scope_id="DIVIDEND",
        strategy_id="DIVIDEND",
        audit_type="WEEKLY_AUDIT",
        completed_at=NOW,
        checks=(AuditCheckResult("paper_only", status, "paper boundary verified"),),
    )


def test_strategy_audit_requires_strategy_id():
    model = AuditModel("STRATEGY", "DIVIDEND", "WEEKLY_AUDIT", NOW, (AuditCheckResult("x", FindingStatus.PASS, "ok"),))
    with pytest.raises(PlatformValidationError):
        model.validate()


def test_platform_audit_rejects_strategy_id():
    model = AuditModel("PLATFORM", "PLATFORM", "RELEASE_AUDIT", NOW, (AuditCheckResult("x", FindingStatus.PASS, "ok"),), "DIVIDEND")
    with pytest.raises(PlatformValidationError):
        model.validate()


def test_audit_requires_timezone_aware_timestamp():
    model = AuditModel("PLATFORM", "PLATFORM", "RELEASE_AUDIT", datetime(2026, 1, 1), (AuditCheckResult("x", FindingStatus.PASS, "ok"),))
    with pytest.raises(PlatformValidationError):
        model.validate()


def test_renderer_uses_strategy_isolated_path():
    assert AuditRenderer().output_directory(strategy_model()).as_posix() == "results/dividend/audits/weekly_audit"


def test_renderer_builds_canonical_audit_run():
    run = AuditRenderer().build_audit_run(strategy_model())
    assert run.strategy_id == "DIVIDEND"
    assert run.findings[0].status is FindingStatus.PASS


def test_json_and_markdown_are_deterministic_and_scoped():
    renderer = AuditRenderer()
    model = strategy_model()
    assert renderer.render_json(model) == renderer.render_json(model)
    markdown = renderer.render_markdown(model)
    assert "Strategy: DIVIDEND" in markdown
    assert "[PASS] paper_only" in markdown


def test_release_gate_fails_on_failed_check():
    result = evaluate_release_gate((strategy_model(FindingStatus.FAIL),))
    assert result.passed is False
    assert result.failures == ("WEEKLY_AUDIT:paper_only",)


def test_release_gate_allows_warnings_but_reports_them():
    result = evaluate_release_gate((strategy_model(FindingStatus.WARNING),))
    assert result.passed is True
    assert result.warnings == ("WEEKLY_AUDIT:paper_only",)


def test_release_gate_requires_models():
    with pytest.raises(PlatformValidationError):
        evaluate_release_gate(())


def test_platform_and_strategy_audits_cannot_be_combined():
    platform = AuditModel("PLATFORM", "PLATFORM", "RELEASE_AUDIT", NOW, (AuditCheckResult("x", FindingStatus.PASS, "ok"),))
    with pytest.raises(PlatformValidationError):
        ensure_single_audit_scope((platform, strategy_model()))
