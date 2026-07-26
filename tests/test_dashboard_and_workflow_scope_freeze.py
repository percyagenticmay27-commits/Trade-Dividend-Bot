from pathlib import Path


FREEZE_PATH = Path("docs/DASHBOARD_AND_WORKFLOW_SCOPE_FREEZE.md")


def test_scope_freeze_document_exists():
    assert FREEZE_PATH.is_file()


def test_all_platform_surfaces_have_single_responsibilities():
    text = FREEZE_PATH.read_text(encoding="utf-8")
    required = (
        "Enterprise AI CIO Portal",
        "Executive Dashboard",
        "Investor Dashboard",
        "Dividend Strategy Dashboard",
        "Cash Account Workflow",
        "Allocation Center",
        "Plugin Discovery",
    )
    for heading in required:
        assert f"### {heading}" in text


def test_single_source_of_truth_rule_is_frozen():
    text = FREEZE_PATH.read_text(encoding="utf-8")
    assert "calculated once by their owning service" in text
    assert "rather than creating competing calculations" in text


def test_scope_creep_is_blocked_before_deployment():
    text = FREEZE_PATH.read_text(encoding="utf-8")
    assert "No new dashboard or workflow may be added" in text
    assert "The remaining path is acceptance validation" in text


def test_investor_controls_future_live_mode():
    text = FREEZE_PATH.read_text(encoding="utf-8")
    assert "Only the investor may authorize a future transition to live mode" in text
    assert "Robinhood or Agentic integration is deferred" in text
