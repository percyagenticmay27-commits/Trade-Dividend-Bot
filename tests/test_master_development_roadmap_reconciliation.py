from pathlib import Path


ROADMAP_PATH = Path("docs/MASTER_DEVELOPMENT_ROADMAP.md")


def _roadmap_text() -> str:
    return ROADMAP_PATH.read_text(encoding="utf-8")


def test_roadmap_exists() -> None:
    assert ROADMAP_PATH.is_file()


def test_platform_v1_dividend_is_complete() -> None:
    text = _roadmap_text()
    assert "### Platform V1 Dividend — Complete" in text
    assert "12. Platform V1 Dividend Freeze" in text
    assert "13. Cloud Readiness and Deployment Foundation" in text
    assert "14. Paper Production Acceptance" in text
    assert "15. Platform V1 Release" in text


def test_enterprise_ai_cio_v1_is_complete() -> None:
    text = _roadmap_text()
    assert "### Enterprise Core and AI CIO Version 1 — Complete" in text
    assert "10. Strategy Inventory Service" in text
    assert "18. Enterprise AI CIO Release Readiness" in text
    assert "Complete Stage 10–18 regression suite: 115 passed" in text
    assert "Failures: 0" in text
    assert "Errors: 0" in text


def test_release_references_are_recorded() -> None:
    text = _roadmap_text()
    assert "`v1.0-enterprise-ai-cio`" in text
    assert "`backup/pre-enterprise-ai-cio-v1`" in text
    assert "Current code baseline: `main`" in text


def test_remaining_work_is_operational_only() -> None:
    text = _roadmap_text()
    assert "The remaining work is deployment and operational validation, not new feature development." in text
    assert "DigitalOcean Production Verification" in text
    assert "Scheduler and Email Verification" in text
    assert "Restart and Recovery Verification" in text
    assert "Deployed Paper Production Acceptance" in text


def test_safety_boundaries_remain_locked() -> None:
    text = _roadmap_text()
    assert "`paper_trade_mode=True`" in text
    assert "`live_trading_enabled=False`" in text
    assert "`broker_execution_enabled=False`" in text
    assert "No real order placement" in text
    assert "No automatic capital movement" in text


def test_swing_deployment_remains_deferred() -> None:
    text = _roadmap_text()
    assert "Swing Bot deployment and Enterprise registration" in text
    assert "Keep Swing deployment deferred until this closeout is complete" in text


def test_stale_roadmap_state_is_removed() -> None:
    text = _roadmap_text()
    assert "### In Progress" not in text
    assert "### Planned" not in text
    assert "`phase-12-platform-v1-dividend-freeze`" not in text
