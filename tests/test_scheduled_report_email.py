from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json

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


def _state(as_of: str) -> dict:
    return {
        "as_of_date": as_of,
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 1.0,
                "b_shares": 1.0,
                "last_prices": {"A": 20.0, "B": 10.0},
                "last_signal": {"A": "BUY", "B": "SELL"},
                "a_in_sgov": False,
                "b_in_sgov": False,
                "a_earnings_lock": False,
                "b_earnings_lock": False,
                "sgov_balance": 45.0,
                "total_dividends_received": 1.0,
            }
        },
    }


def _environment() -> dict[str, str]:
    return {
        "GMAIL_USER": "sender@example.com",
        "GMAIL_APP_PASSWORD": "secret",
        "REPORT_RECIPIENT": "recipient@example.com",
        "DIVIDEND_BOT_TIMEZONE": "America/Chicago",
        "DIVIDEND_DASHBOARD_BASE_URL": "https://example.com",
    }


def test_email_settings_require_all_credentials():
    with pytest.raises(RuntimeError):
        configured_email_settings({"GMAIL_USER": "a@example.com"})


def test_email_settings_use_environment_values():
    settings = configured_email_settings(_environment())
    assert settings["sender"] == "sender@example.com"
    assert settings["recipient"] == "recipient@example.com"
    assert settings["dashboard_base_url"] == "https://example.com"
    assert settings["daily_state_max_age_days"] == "5"


def test_every_day_at_seven_is_daily_due():
    now = datetime(2026, 8, 5, 19, 0, tzinfo=TZ)
    assert due_report_frequencies(now) == ["daily"]


def test_friday_at_seven_is_daily_and_weekly_due():
    now = datetime(2026, 7, 31, 19, 0, tzinfo=TZ)
    assert "daily" in due_report_frequencies(now)
    assert "weekly" in due_report_frequencies(now)


def test_last_day_at_seven_is_monthly_due():
    now = datetime(2026, 7, 31, 19, 0, tzinfo=TZ)
    assert "monthly" in due_report_frequencies(now)
    assert is_last_calendar_day(now) is True


def test_non_due_hour_returns_empty():
    now = datetime(2026, 7, 31, 18, 0, tzinfo=TZ)
    assert due_report_frequencies(now) == []


def test_month_end_that_is_not_friday_sends_daily_and_monthly():
    now = datetime(2026, 8, 31, 19, 0, tzinfo=TZ)
    assert due_report_frequencies(now) == ["daily", "monthly"]


def test_dashboard_links_are_secure_paths():
    links = dict(dashboard_links("https://dividend.example.com"))
    assert links["Executive Dashboard"].startswith("https://")
    assert links["Monthly Reports"].endswith("/reports/monthly/")


def test_existing_attachments_skips_missing_files(tmp_path: Path):
    report = tmp_path / "weekly_portfolio_review.md"
    report.write_text("# Weekly", encoding="utf-8")
    found = existing_attachments(tmp_path, ["weekly_portfolio_review.md", "missing.html"])
    assert found == [report]


def test_message_contains_csv_attachment(tmp_path: Path):
    report = tmp_path / "dividend_portfolio.csv"
    report.write_text("symbol,price\nTEST,1\n", encoding="utf-8")
    message = build_report_message(
        frequency="daily",
        sender="sender@example.com",
        recipient="recipient@example.com",
        report_date="2026-08-05",
        attachments=[report],
        links=[],
    )
    assert "PAPER ONLY" in message.get_body(preferencelist=("plain",)).get_content()
    attachment = next(message.iter_attachments())
    assert attachment.get_filename() == report.name
    assert attachment.get_content_type() == "text/csv"


def test_invalid_frequency_is_rejected():
    with pytest.raises(ValueError):
        build_report_message(
            frequency="hourly",
            sender="a@example.com",
            recipient="b@example.com",
            report_date="2026-07-31",
            attachments=[],
        )


def test_send_scheduled_reports_sends_daily_weekly_and_monthly_together(tmp_path: Path):
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(_state("2026-07-31")), encoding="utf-8"
    )
    (tmp_path / "weekly_portfolio_review.md").write_text("# Weekly", encoding="utf-8")
    sent_messages = []

    def fake_sender(message, *, password):
        sent_messages.append((message, password))

    sent = send_scheduled_reports(
        root_dir=tmp_path,
        now=datetime(2026, 7, 31, 19, 0, tzinfo=TZ),
        environment=_environment(),
        smtp_sender=fake_sender,
    )
    assert sent == ["daily", "weekly", "monthly"]
    assert len(sent_messages) == 3
    daily_message = sent_messages[0][0]
    assert sorted(part.get_filename() for part in daily_message.iter_attachments()) == [
        "dividend_executive_summary.csv",
        "dividend_portfolio.csv",
        "dividend_watchlist.csv",
    ]
    assert all(password == "secret" for _, password in sent_messages)


def test_stale_daily_state_blocks_email(tmp_path: Path):
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(_state("2026-06-01")), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="stale"):
        send_scheduled_reports(
            root_dir=tmp_path,
            now=datetime(2026, 8, 5, 19, 0, tzinfo=TZ),
            environment=_environment(),
            smtp_sender=lambda *_args, **_kwargs: None,
        )


def test_safety_constants_are_locked():
    from src.dividend_bot import scheduled_report_email as module

    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
