"""Validate the ETF daily decision report CSV email without network access."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from send_daily_reports import EXPECTED_CSV_NAMES, send_daily_reports


def _write_inputs(root: Path) -> None:
    (root / "paper_state.json").write_text(
        json.dumps({"as_of_date": "2026-08-05"}), encoding="utf-8"
    )
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
            rows = list(csv.DictReader(handle))
        assert rows
        assert rows[0]["source_file"].endswith(".md")
        assert rows[0]["paper_trade_mode"] == "True"


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
