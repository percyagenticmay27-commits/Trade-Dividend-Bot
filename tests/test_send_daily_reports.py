"""Validate the ETF daily decision report CSV email without network access."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from send_daily_reports import EXPECTED_CSV_NAMES, send_daily_reports
from src.dividend_bot.executive_daily_change_summary import DAILY_CHANGE_FIELDS
from src.dividend_bot.executive_daily_paper_report import DAILY_PAPER_FIELDS
from src.dividend_bot.executive_strategy_health_report import STRATEGY_HEALTH_FIELDS


EXPECTED_EXECUTIVE_FIELDS = [
    "report_section",
    "field",
    "value",
    "report_text",
    "source_line",
    "paper_trade_mode",
]


def _write_inputs(root: Path) -> None:
    state = {
        "paper_only": True,
        "as_of_date": "2026-08-05",
        "starting_capital": 500.0,
        "pairs": {
            "AMDW / AMDL": {
                "a_ticker": "AMDW",
                "b_ticker": "AMDL",
                "a_shares": 1.0,
                "b_shares": 1.0,
                "a_in_sgov": False,
                "b_in_sgov": False,
                "sgov_balance": 0.0,
                "last_prices": {"A": 10.0, "B": 5.0},
                "last_signal": {"A": "BUY", "B": "BUY"},
                "last_action": "NO_PAPER_TRADE",
                "total_dividends_received": 0.0,
            }
        },
    }
    (root / "paper_state.json").write_text(json.dumps(state), encoding="utf-8")
    reports = {
        "daily_paper_report.md": "# Daily Paper Report\n- Status: READY\n",
        "daily_change_summary.md": "# Daily Change Summary\n- Change: NONE\n",
        "strategy_health_report.md": "# Strategy Health Report\n- Health: GOOD\n",
        "live_readiness_report.md": "# Live Readiness Report\n- Ready: NO\n",
    }
    for name, content in reports.items():
        (root / name).write_text(content, encoding="utf-8")


def test_daily_decision_email_converts_exact_markdown_reports_to_csv(tmp_path: Path):
    _write_inputs(tmp_path)
    sent: list[dict] = []

    def fake_email_sender(**kwargs):
        sent.append(kwargs)

    result = send_daily_reports(
        root_dir=tmp_path,
        delivery_log=Path("email_delivery_test.csv"),
        sender="sender@example.com",
        recipient="recipient@example.com",
        email_sender=fake_email_sender,
    )

    assert result == "SENT"
    assert len(sent) == 1
    payload = sent[0]
    assert payload["subject"] == "PAPER ONLY ETF Daily Decision Reports - 2026-08-05"
    assert [path.name for path in payload["attachments"]] == list(EXPECTED_CSV_NAMES)
    assert all(path.suffix == ".csv" and path.is_file() for path in payload["attachments"])

    for path in payload["attachments"]:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)

        assert rows
        assert "source_file" not in rows[0]
        assert "row_type" not in rows[0]
        assert "label" not in rows[0]

        if path.name == "daily_paper_report.csv":
            assert reader.fieldnames == DAILY_PAPER_FIELDS
            assert all(row["paper_trade_mode"] == "True" for row in rows)
            assert any(row["report_section"] == "Executive Header" for row in rows)
            assert any(row["report_section"] == "Portfolio Summary" for row in rows)
            assert any(row["report_section"] == "Current Pair Holdings" for row in rows)
            assert any(row["metric"] == "Starting Capital" and row["value"] == "$50,000.00" for row in rows)
        elif path.name == "daily_change_summary.csv":
            assert reader.fieldnames == DAILY_CHANGE_FIELDS
            assert any(row["event"] == "Report Name" for row in rows)
            assert any(row["event"] == "Purpose" for row in rows)
            assert any(row["event"] == "No portfolio changes" for row in rows)
        elif path.name == "strategy_health_report.csv":
            assert reader.fieldnames == STRATEGY_HEALTH_FIELDS
            content_rows = [row for row in rows if any(row.values())]
            assert all(row["paper_trade_mode"] == "True" for row in content_rows)
            assert any(not any(row.values()) for row in rows)
            assert any(row["report_section"] == "Portfolio Health" for row in rows)
            assert any(row["report_section"] == "Pair Performance" for row in rows)
            assert any(row["report_section"] == "Deployment Gates" for row in rows)
            assert any(row["metric"] == "Starting Capital" and row["value"] == "$50,000.00" for row in rows)
            assert any(row["metric"] == "Dividends Received" for row in rows)
            assert any(row["metric"] == "Total Return Amount" for row in rows)
            assert any(row["metric"] == "Total Portfolio Value" for row in rows)
        else:
            assert reader.fieldnames == EXPECTED_EXECUTIVE_FIELDS
            assert all(row["paper_trade_mode"] == "True" for row in rows)
            assert any(row["report_section"] == "Executive Header" for row in rows)
            assert any(row["report_section"] == "What This Report Shows" for row in rows)
            assert any(row["report_section"] == "Why This Report Is Used" for row in rows)
            assert any(row["source_line"] for row in rows)


def test_daily_decision_email_duplicate_protection(tmp_path: Path):
    _write_inputs(tmp_path)
    sent: list[dict] = []

    first = send_daily_reports(
        root_dir=tmp_path,
        delivery_log=Path("email_delivery_test.csv"),
        sender="sender@example.com",
        recipient="recipient@example.com",
        email_sender=lambda **kwargs: sent.append(kwargs),
    )
    second = send_daily_reports(
        root_dir=tmp_path,
        delivery_log=Path("email_delivery_test.csv"),
        sender="sender@example.com",
        recipient="recipient@example.com",
        email_sender=lambda **kwargs: sent.append(kwargs),
    )

    assert first == "SENT"
    assert second == "SKIPPED_ALREADY_SENT"
    assert len(sent) == 1


def test_missing_authoritative_markdown_report_blocks_email(tmp_path: Path):
    _write_inputs(tmp_path)
    (tmp_path / "live_readiness_report.md").unlink()

    try:
        send_daily_reports(
            root_dir=tmp_path,
            delivery_log=Path("email_delivery_test.csv"),
            sender="sender@example.com",
            recipient="recipient@example.com",
            email_sender=lambda **_kwargs: None,
        )
    except RuntimeError as exc:
        assert "live_readiness_report.md" in str(exc)
    else:
        raise AssertionError("Missing required Markdown report should block delivery")
