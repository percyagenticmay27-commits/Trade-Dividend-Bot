from pathlib import Path


FREEZE_PATH = Path("docs/PLATFORM_V1_DIVIDEND_FREEZE.md")


def _freeze_text() -> str:
    return FREEZE_PATH.read_text(encoding="utf-8")


def test_freeze_document_exists():
    assert FREEZE_PATH.exists()


def test_freeze_document_declares_platform_v1_freeze():
    text = _freeze_text()
    assert "# Platform V1 Dividend Freeze" in text
    assert "feature set is frozen" in text


def test_permanent_paper_only_safety_boundaries_are_documented():
    text = _freeze_text()
    for required in (
        "`paper_trade_mode=True`",
        "`live_trading_enabled=False`",
        "`broker_execution_enabled=False`",
        "No real order placement",
        "No automatic capital movement",
    ):
        assert required in text


def test_human_approval_and_advisory_only_rules_are_documented():
    text = _freeze_text()
    assert "Enterprise AI CIO output is advisory only" in text
    assert "Investor approval is required" in text


def test_learning_is_append_only_and_cannot_change_policy():
    text = _freeze_text()
    assert "Learning records are append-only" in text
    assert "cannot silently change policy" in text


def test_duplicate_event_protection_is_documented():
    text = _freeze_text()
    assert "Duplicate events cannot create duplicate governed records" in text
    assert "duplicate-event suppression" in text


def test_frozen_dependency_order_contains_all_governed_layers():
    text = _freeze_text()
    for layer in (
        "Enterprise Dividend Dashboard",
        "Enterprise Investor Dashboard",
        "Enterprise Dividend Alerts",
        "Enterprise Dividend Reviews",
        "Enterprise Dividend Learning",
        "Enterprise Dividend CIO Advisory",
        "Enterprise Dividend Replacement Analysis",
        "Enterprise Dividend Strategy Health",
        "Enterprise Dividend Daily Cycle",
        "Service Registry and Event Wiring",
    ):
        assert layer in text


def test_all_phase_two_through_eleven_validation_totals_are_recorded():
    text = _freeze_text()
    for total in (24, 28, 30, 26, 28, 26, 29, 26, 29, 13):
        assert f"{total} passed" in text
    assert "259 passing tests across Phases 2 through 11" in text


def test_phase_one_unknown_test_total_is_disclosed():
    text = _freeze_text()
    assert "Phase 1" in text
    assert "test total was not recorded" in text


def test_review_status_vocabulary_is_frozen():
    text = _freeze_text()
    for status in ("`OPEN`", "`UNDER_REVIEW`", "`RESOLVED`", "`DEFERRED`", "`ESCALATED`"):
        assert status in text


def test_cio_recommendation_vocabulary_is_frozen():
    text = _freeze_text()
    for recommendation in ("`HOLD`", "`REVIEW`", "`REDUCE`", "`EXIT_REVIEW`", "`REPLACEMENT_REVIEW`"):
        assert recommendation in text


def test_strategy_health_status_vocabulary_is_frozen():
    text = _freeze_text()
    for status in ("`HEALTHY`", "`WATCH`", "`DEGRADED`", "`CRITICAL`"):
        assert status in text


def test_daily_cycle_status_vocabulary_is_frozen():
    text = _freeze_text()
    for status in ("`PLANNED`", "`COMPLETED`", "`COMPLETED_WITH_WARNINGS`", "`FAILED`"):
        assert status in text


def test_known_limitations_are_documented():
    text = _freeze_text()
    assert "## Known Platform V1 Limitations" in text
    assert "does not run registered services" in text
    assert "aggregates supplied step results" in text


def test_allowed_post_freeze_changes_are_restricted():
    text = _freeze_text()
    assert "## Allowed Post-Freeze Changes" in text
    assert "Defect corrections" in text
    assert "requires explicit review and a documented version decision" in text


def test_version_two_scope_is_explicitly_deferred():
    text = _freeze_text()
    for deferred in (
        "Live brokerage execution",
        "Swing strategy integration",
        "Options strategy integration",
        "Futures strategy integration",
        "Autonomous replacement execution",
    ):
        assert deferred in text


def test_remaining_release_gates_are_documented():
    text = _freeze_text()
    assert "Cloud Readiness and Deployment" in text
    assert "Paper Production Acceptance Test" in text
    assert "Platform V1 Release" in text
