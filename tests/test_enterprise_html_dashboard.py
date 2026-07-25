from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.enterprise_html_dashboard import (
    BROKER_EXECUTION_ENABLED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    build_html_portal,
    render_dashboard_html,
)


def test_safety_constants_are_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False


def test_render_contains_paper_only_banner_and_navigation():
    page = render_dashboard_html(
        title="Executive Dashboard",
        report={"summary": {"annual_income": 1200.0, "confidence_score": 88}},
        navigation=[("Executive", "executive_dashboard.html")],
        generated_at_utc="2026-07-25T20:00:00Z",
    )
    assert "PAPER ONLY" in page
    assert "No live orders" in page
    assert "executive_dashboard.html" in page
    assert "Annual Income" in page
    assert "1,200.00" in page


def test_render_escapes_untrusted_values():
    page = render_dashboard_html(
        title="<script>alert(1)</script>",
        report={"summary": {"message": "<b>unsafe</b>"}},
        navigation=[],
    )
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<b>unsafe</b>" not in page


def test_render_includes_ai_cio_commentary():
    page = render_dashboard_html(
        title="Strategy Health",
        report={"summary": {"status": "HEALTHY"}, "commentary": "Income quality remained stable."},
        navigation=[],
    )
    assert "AI CIO Commentary" in page
    assert "Income quality remained stable." in page


def test_build_portal_generates_index_and_pages(tmp_path: Path):
    reports = tmp_path / "results"
    output = tmp_path / "html"
    reports.mkdir()
    (reports / "executive.json").write_text(
        json.dumps({"summary": {"portfolio_value": 500.0}}), encoding="utf-8"
    )
    result = build_html_portal(
        reports_dir=reports,
        output_dir=output,
        report_specs=(("Executive Dashboard", "executive.json", "executive_dashboard.html"),),
        generated_at_utc="2026-07-25T20:00:00Z",
    )
    assert Path(result["index_path"]).is_file()
    assert (output / "executive_dashboard.html").is_file()
    assert result["warnings"] == []
    assert result["paper_trade_mode"] is True


def test_missing_source_generates_page_and_warning(tmp_path: Path):
    result = build_html_portal(
        reports_dir=tmp_path / "missing",
        output_dir=tmp_path / "html",
        report_specs=(("Investor Dashboard", "missing.json", "investor_dashboard.html"),),
    )
    assert len(result["warnings"]) == 1
    assert Path(result["generated_pages"][0]["path"]).is_file()


def test_index_links_to_all_pages(tmp_path: Path):
    specs = (
        ("Executive Dashboard", "one.json", "executive_dashboard.html"),
        ("Investor Dashboard", "two.json", "investor_dashboard.html"),
    )
    result = build_html_portal(reports_dir=tmp_path, output_dir=tmp_path / "html", report_specs=specs)
    index = Path(result["index_path"]).read_text(encoding="utf-8")
    assert "executive_dashboard.html" in index
    assert "investor_dashboard.html" in index
