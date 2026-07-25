from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.dividend_bot.scheduled_report_email import (
    build_report_message,
    configured_email_settings,
    dashboard_links,
    due_report_frequencies,
    existing_attachments,
    is_last_calendar_day,
    send_scheduled_reports,
)


TZ = ZoneInfo("America/Chicago")


def test_email_settings_require_all_credentials():
    with pytest.raises(RuntimeError):
        configured_email_settings({"GMAIL_USER": "a@example.com"})


def test_email_settings_use_environment_values():
    settings = configured_email_settings({
        "GMAIL_USER": "sender@example.com",
        "GMAIL_APP_PASSWORD": "secret",
        "REPORT_RECIPIENT": "recipient@example.com",
        "DIVIDEND_BOT_TIMEZONE": "America/Chicago",
        "DIVIDEND_DASHBOARD_BASE_URL": "https://example.com/",
    })
    assert settings["sender"] == "sender@example.com"
    assert settings["recipient"] == "recipient@example.com"
    assert settings["dashboard_base_url"] == "https://example.com"


def test_friday_at_seven_is_weekly_due():
    now = datetime(2026, 7, 31, 19, 0, tzinfo=TZ)
    assert "weekly" in due_report_frequencies(now)


def test_last_day_at_seven_is_monthly_due():
    now = datetime(2026, 7, 31, 19, 0, tzinfo=TZ)
    assert "monthly" in due_report_frequencies(now)
    assert is_last_calendar_day(now) is True


def test_non_due_hour_returns_empty():
    now = datetime(2026, 7, 31, 18, 0, tzinfo=TZ)
    assert due_report_frequencies(now) == []


def test_month_end_that_is_not_friday_only_sends_monthly():
    now = datetime(2026, 8, 31, 19, 0, tzinfo=TZ)
    assert due_report_frequencies(now) == ["monthly"]


def test_dashboard_links_are_secure_paths():
    links = dict(dashboard_links("https://dividend.example.com"))
    assert links["Executive Dashboard"].startswith("https://")
    assert links["Monthly Reports"].endswith("/reports/monthly/")


def test_existing_attachments_skips_missing_files(tmp_path: Path):
    report = tmp_path / "weekly_portfolio_review.md"
    report.write_text("# Weekly", encoding="utf-8")
    found = existing_attachments(tmp_path, ["weekly_portfolio_review.md", "missing.html"])
    assert found == [report]


def test_message_contains_links_and_attachments(tmp_path: Path):
    report = tmp_path / "weekly_portfolio_review.md"
    report.write_text("# Weekly", encoding="utf-8")
    message = build_report_message(
        frequency="weekly",
        sender="sender@example.com",
        recipient="recipient@example.com",
        report_date="2026-07-31",
        attachments=[report],
        links=[("Executive Dashboard", "https://example.com/executive_dashboard.html")],
    )
    assert "PAPER ONLY" in message.get_body(preferencelist=("plain",)).get_content()
    assert message["To"] == "recipient@example.com"
    assert any(part.get_filename() == report.name for part in message.iter_attachments())


def test_invalid_frequency_is_rejected():
    with pytest.raises(ValueError):
        build_report_message(
            frequency="daily",
            sender="a@example.com",
            recipient="b@example.com",
            report_date="2026-07-31",
            attachments=[],
        )


def test_send_scheduled_reports_can_send_weekly_and_monthly_together(tmp_path: Path):
    (tmp_path / "weekly_portfolio_review.md").write_text("# Weekly", encoding="utf-8")
    sent_messages = []

    def fake_sender(message, *, password):
        sent_messages.append((message, password))

    sent = send_scheduled_reports(
        root_dir=tmp_path,
        now=datetime(2026, 7, 31, 19, 0, tzinfo=TZ),
        environment={
            "GMAIL_USER": "sender@example.com",
            "GMAIL_APP_PASSWORD": "secret",
            "REPORT_RECIPIENT": "recipient@example.com",
            "DIVIDEND_BOT_TIMEZONE": "America/Chicago",
            "DIVIDEND_DASHBOARD_BASE_URL": "https://example.com",
        },
        smtp_sender=fake_sender,
    )
    assert sent == ["weekly", "monthly"]
    assert len(sent_messages) == 2
    assert all(password == "secret" for _, password in sent_messages)


def test_safety_constants_are_locked():
    from src.dividend_bot import scheduled_report_email as module

    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
