"""Scheduled Gmail delivery for weekly and monthly paper-only reports."""
from __future__ import annotations

import calendar
import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

MODULE_NAME = "scheduled_report_email"
MODULE_VERSION = "1.0.2"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

DEFAULT_TIMEZONE = "America/Chicago"
DEFAULT_SEND_HOUR = 19
WEEKLY_REPORT_FILES = (
    "weekly_portfolio_review.md",
    "results/html/executive_dashboard.html",
    "results/html/investor_dashboard.html",
    "results/html/strategy_health.html",
    "results/html/cio_advisory.html",
)
MONTHLY_REPORT_FILES = (
    "results/monthly_board_report.html",
    "results/html/executive_dashboard.html",
    "results/html/investor_dashboard.html",
    "results/html/strategy_health.html",
    "results/html/learning.html",
    "results/html/cio_advisory.html",
)


def configured_email_settings(environment: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    values = dict(os.environ if environment is None else environment)
    required = ("GMAIL_USER", "GMAIL_APP_PASSWORD", "REPORT_RECIPIENT")
    missing = [name for name in required if not str(values.get(name, "")).strip()]
    if missing:
        raise RuntimeError("Missing required email environment variables: " + ", ".join(missing))
    return {
        "sender": str(values["GMAIL_USER"]).strip(),
        "password": str(values["GMAIL_APP_PASSWORD"]).strip(),
        "recipient": str(values["REPORT_RECIPIENT"]).strip(),
        "timezone": str(values.get("DIVIDEND_BOT_TIMEZONE") or DEFAULT_TIMEZONE).strip(),
        "dashboard_base_url": str(values.get("DIVIDEND_DASHBOARD_BASE_URL") or "").rstrip("/"),
    }


def is_last_calendar_day(moment: datetime) -> bool:
    return moment.day == calendar.monthrange(moment.year, moment.month)[1]


def due_report_frequencies(
    now: Optional[datetime] = None,
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    send_hour: int = DEFAULT_SEND_HOUR,
) -> list[str]:
    zone = ZoneInfo(timezone_name)
    current = now.astimezone(zone) if now is not None else datetime.now(zone)
    if current.hour != send_hour:
        return []
    due: list[str] = []
    if current.weekday() == 4:
        due.append("weekly")
    if is_last_calendar_day(current):
        due.append("monthly")
    return due


def existing_attachments(root_dir: str | Path, names: Sequence[str]) -> list[Path]:
    root = Path(root_dir)
    return [root / name for name in names if (root / name).is_file()]


def dashboard_links(base_url: str) -> list[tuple[str, str]]:
    if not base_url:
        return []
    return [
        ("AI CIO Portal", f"{base_url}/index.html"),
        ("Executive Dashboard", f"{base_url}/executive_dashboard.html"),
        ("Investor Dashboard", f"{base_url}/investor_dashboard.html"),
        ("Strategy Health", f"{base_url}/strategy_health.html"),
        ("CIO Advisory", f"{base_url}/cio_advisory.html"),
        ("Learning", f"{base_url}/learning.html"),
        ("Weekly Reports", f"{base_url}/reports/weekly/"),
        ("Monthly Reports", f"{base_url}/reports/monthly/"),
    ]


def build_report_message(
    *,
    frequency: str,
    sender: str,
    recipient: str,
    report_date: str,
    attachments: Sequence[Path],
    links: Sequence[tuple[str, str]] = (),
) -> EmailMessage:
    normalized = frequency.lower()
    if normalized not in {"weekly", "monthly"}:
        raise ValueError("frequency must be weekly or monthly")
    title = normalized.title()
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"PAPER ONLY Dividend Bot {title} Report - {report_date}"
    text_lines = [
        "PAPER ONLY - NO REAL TRADES EXECUTED",
        "",
        f"The {normalized} Dividend Bot reporting cycle is complete.",
    ]
    if links:
        text_lines.extend(["", "Secure dashboard links:"])
        text_lines.extend(f"- {label}: {url}" for label, url in links)
    if attachments:
        text_lines.extend(["", "Attached reports:"])
        text_lines.extend(f"- {path.name}" for path in attachments)
    message.set_content("\n".join(text_lines) + "\n")

    link_html = "".join(
        f'<li><a href="{url}">{label}</a></li>' for label, url in links
    ) or "<li>No dashboard URL configured.</li>"
    attachment_html = "".join(f"<li>{path.name}</li>" for path in attachments) or "<li>No attachments were available.</li>"
    message.add_alternative(
        f"""
        <html><body>
        <h2>Dividend Bot {title} Report</h2>
        <p><strong>PAPER ONLY - NO REAL TRADES EXECUTED</strong></p>
        <p>The {normalized} reporting cycle is complete for {report_date}.</p>
        <h3>Secure dashboard links</h3><ul>{link_html}</ul>
        <h3>Attached reports</h3><ul>{attachment_html}</ul>
        </body></html>
        """,
        subtype="html",
    )
    for path in attachments:
        maintype, subtype = ("text", "html") if path.suffix.lower() == ".html" else ("text", "markdown")
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return message


def send_report_message(message: EmailMessage, *, password: str) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as smtp:
        smtp.login(str(message["From"]), password)
        smtp.send_message(message)


def send_scheduled_reports(
    *,
    root_dir: str | Path = ".",
    now: Optional[datetime] = None,
    environment: Optional[Mapping[str, str]] = None,
    smtp_sender=send_report_message,
) -> list[str]:
    settings = configured_email_settings(environment)
    zone = ZoneInfo(settings["timezone"])
    current = now.astimezone(zone) if now is not None else datetime.now(zone)
    sent: list[str] = []
    for frequency in due_report_frequencies(current, timezone_name=settings["timezone"]):
        names = WEEKLY_REPORT_FILES if frequency == "weekly" else MONTHLY_REPORT_FILES
        attachments = existing_attachments(root_dir, names)
        message = build_report_message(
            frequency=frequency,
            sender=settings["sender"],
            recipient=settings["recipient"],
            report_date=current.date().isoformat(),
            attachments=attachments,
            links=dashboard_links(settings["dashboard_base_url"]),
        )
        smtp_sender(message, password=settings["password"])
        sent.append(frequency)
    return sent


def main() -> int:
    sent = send_scheduled_reports()
    print("Scheduled report email result: " + (", ".join(sent) if sent else "NOT_DUE"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
