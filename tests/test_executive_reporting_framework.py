from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.dividend_bot.daily_markdown_report_csv import markdown_rows
from src.dividend_bot.executive_reporting_framework import (
    REPORT_VERSION,
    STANDARD_SECTION_ORDER,
    executive_framework_rows,
    executive_metadata,
    report_definition,
)


def test_all_four_daily_reports_have_definitions():
    expected = {
        "daily_paper_report.md": "Daily Paper Report",
        "daily_change_summary.md": "Daily Change Summary",
        "strategy_health_report.md": "Strategy Health Report",
        "live_readiness_report.md": "Live Readiness Report",
    }
    for source, title in expected.items():
        definition = report_definition(source)
        assert definition.report_name == title
        assert definition.what_it_shows
        assert definition.why_it_is_used


def test_metadata_is_standardized_and_paper_only():
    metadata = executive_metadata(
        source_name="daily_paper_report.md",
        trading_date=date(2026, 8, 5),
        generated_at=datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
    )
    assert metadata["report_version"] == REPORT_VERSION
    assert metadata["trading_date"] == "2026-08-05"
    assert metadata["paper_trading_mode"] is True
    assert metadata["generated_by"] == "TradeBot Dividend Bot"
    assert metadata["safety_statement"] == "PAPER ONLY - NO REAL TRADES EXECUTED"
    assert metadata["standard_section_order"] == " | ".join(STANDARD_SECTION_ORDER)


def test_framework_rows_begin_with_report_identity_and_include_purpose():
    rows = executive_framework_rows(
        source_name="strategy_health_report.md",
        trading_date=date(2026, 8, 5),
        generated_at=datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
    )
    assert rows[0] == {
        "section": "Executive Header",
        "field": "Report Name",
        "value": "Strategy Health Report",
    }
    assert any(row["section"] == "What This Report Shows" for row in rows)
    assert any(row["section"] == "Why This Report Is Used" for row in rows)
    assert rows[-1]["section"] == "Executive Footer"


def test_markdown_csv_rows_prepend_framework_without_changing_report_content(tmp_path: Path):
    report = tmp_path / "daily_change_summary.md"
    report.write_text(
        "# Daily Change Summary\n\n## New Signals\n- Pair: AMDW / AMDL\n- Action: WAITING_TO_BUY\n",
        encoding="utf-8",
    )
    rows = markdown_rows(
        report,
        as_of_date=date(2026, 8, 5),
        generated_at=datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
    )
    assert rows[0]["report_section"] == "Executive Header"
    assert rows[0]["field"] == "Report Name"
    assert rows[0]["value"] == "Daily Change Summary"
    assert any(
        row["report_section"] == "New Signals"
        and row["field"] == "Pair"
        and row["value"] == "AMDW / AMDL"
        for row in rows
    )
    assert any(
        row["report_section"] == "New Signals"
        and row["field"] == "Action"
        and row["value"] == "WAITING_TO_BUY"
        for row in rows
    )


def test_unknown_report_is_rejected():
    with pytest.raises(ValueError, match="Unsupported executive report"):
        report_definition("unknown.md")


def test_safety_constants_are_locked():
    from src.dividend_bot import executive_reporting_framework as module

    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
    assert module.ORDER_PLACEMENT_ENABLED is False
    assert module.CAPITAL_MOVEMENT_ENABLED is False
