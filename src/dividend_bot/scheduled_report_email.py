"""Scheduled delivery for daily, weekly, and monthly paper-only reports."""
from __future__ import annotations

import base64
import calendar
import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

from src.dividend_bot.daily_dividend_csv_exports import generate_daily_dividend_csv_exports

MODULE_NAME = "scheduled_report_email"
MODULE_VERSION = "1.2.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

DEFAULT_TIMEZONE = "America/Chicago"
DEFAULT_SEND_HOUR = 19
SENDGRID_MAIL_URL = "https://api.sendgrid.com/v3/mail/send"
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
    recipient = str(values.get("REPORT_RECIPIENT") or "").strip()
    if not recipient:
        raise RuntimeError("Missing required email environment variables: REPORT_RECIPIENT")

    sendgrid_key = str(values.get("SENDGRID_API_KEY") or "").strip()
    sendgrid_from = str(values.get("SENDGRID_FROM_EMAIL") or "").strip()
    if sendgrid_key:
        missing = []
        if not sendgrid_from:
            missing.append("SENDGRID_FROM_EMAIL")
        if missing:
            raise RuntimeError("Missing required SendGrid environment variables: " + ", ".join(missing))
        return {
            "transport": "SENDGRID",
            "sender": sendgrid_from,
            "sender_name": str(values.get("SENDGRID_FROM_NAME") or "Dividend AI CIO").strip(),
            "reply_to": str(values.get("SENDGRID_REPLY_TO") or "").strip(),
            "api_key": sendgrid_key,
            "password": "",
            "recipient": recipient,
            "timezone": str(values.get("DIVIDEND_BOT_TIMEZONE") or DEFAULT_TIMEZONE).strip(),
            "dashboard_base_url": str(values.get("DIVIDEND_DASHBOARD_BASE_URL") or "").rstrip("/"),
            "daily_state_max_age_days": str(values.get("DIVIDEND_DAILY_STATE_MAX_AGE_DAYS") or "5").strip(),
        }

    required = ("GMAIL_USER", "GMAIL_APP_PASSWORD")
    missing = [name for name in required if not str(values.get(name, "")).strip()]
    if missing:
        raise RuntimeError(
            "Missing required email environment variables: "
            + ", ".join(missing)
            + ". Configure SENDGRID_API_KEY/SENDGRID_FROM_EMAIL or Gmail credentials."
        )
    return {
        "transport": "GMAIL_SMTP",
        "sender": str(values["GMAIL_USER"]).strip(),
        "sender_name": "",
        "reply_to": "",
        "api_key": "",
        "password": str(values["GMAIL_APP_PASSWORD"]).strip(),
        "recipient": recipient,
        "timezone": str(values.get("DIVIDEND_BOT_TIMEZONE") or DEFAULT_TIMEZONE).strip(),
        "dashboard_base_url": str(values.get("DIVIDEND_DASHBOARD_BASE_URL") or "").rstrip("/"),
        "daily_state_max_age_days": str(values.get("DIVIDEND_DAILY_STATE_MAX_AGE_DAYS") or "5").strip(),
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
    due: list[str] = ["daily"]
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
    if normalized not in {"daily", "weekly", "monthly"}:
        raise ValueError("frequency must be daily, weekly, or monthly")
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
    if normalized == "daily":
        text_lines.extend([
            "",
            "The attached CSV files contain the fresh Dividend strategy executive summary, performance, portfolio, and watchlist.",
        ])
    if links:
        text_lines.extend(["", "Secure dashboard links:"])
        text_lines.extend(f"- {label}: {url}" for label, url in links)
    if attachments:
        text_lines.extend(["", "Attached reports:"])
        text_lines.extend(f"- {path.name}" for path in attachments)
    message.set_content("\n".join(text_lines) + "\n")

    link_html = "".join(f'<li><a href="{url}">{label}</a></li>' for label, url in links) or "<li>No dashboard URL configured.</li>"
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
        suffix = path.suffix.lower()
        if suffix == ".html":
            maintype, subtype = "text", "html"
        elif suffix == ".csv":
            maintype, subtype = "text", "csv"
        else:
            maintype, subtype = "text", "markdown"
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return message


def send_report_message(message: EmailMessage, *, password: str) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as smtp:
        smtp.login(str(message["From"]), password)
        smtp.send_message(message)


def _message_text_parts(message: EmailMessage) -> tuple[str, str]:
    plain = ""
    html = ""
    for part in message.walk():
        if part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() == "text/plain" and not plain:
            plain = part.get_content()
        elif part.get_content_type() == "text/html" and not html:
            html = part.get_content()
    return plain, html


def send_sendgrid_message(
    message: EmailMessage,
    *,
    api_key: str,
    sender_name: str = "",
    reply_to: str = "",
    timeout: int = 30,
) -> None:
    """Send an EmailMessage through SendGrid without exposing credentials."""
    plain, html = _message_text_parts(message)
    payload: dict[str, object] = {
        "personalizations": [{"to": [{"email": str(message["To"])}]}],
        "from": {"email": str(message["From"])},
        "subject": str(message["Subject"]),
        "content": [
            {"type": "text/plain", "value": plain},
            {"type": "text/html", "value": html or plain},
        ],
    }
    if sender_name:
        payload["from"] = {"email": str(message["From"]), "name": sender_name}
    if reply_to:
        payload["reply_to"] = {"email": reply_to}

    attachments = []
    for part in message.iter_attachments():
        raw = part.get_payload(decode=True) or b""
        attachments.append({
            "content": base64.b64encode(raw).decode("ascii"),
            "type": part.get_content_type(),
            "filename": part.get_filename() or "attachment",
            "disposition": "attachment",
        })
    if attachments:
        payload["attachments"] = attachments

    request = urllib.request.Request(
        SENDGRID_MAIL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Trade-Dividend-Bot-Scheduled-Reports/1.2",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            if status < 200 or status >= 300:
                raise RuntimeError(f"SendGrid email delivery failed with HTTP {status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"SendGrid email delivery failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"SendGrid email delivery failed: {exc.reason}") from exc


def send_scheduled_reports(
    *,
    root_dir: str | Path = ".",
    now: Optional[datetime] = None,
    environment: Optional[Mapping[str, str]] = None,
    smtp_sender=send_report_message,
    sendgrid_sender=send_sendgrid_message,
) -> list[str]:
    settings = configured_email_settings(environment)
    zone = ZoneInfo(settings["timezone"])
    current = now.astimezone(zone) if now is not None else datetime.now(zone)
    sent: list[str] = []
    for frequency in due_report_frequencies(current, timezone_name=settings["timezone"]):
        if frequency == "daily":
            attachments = generate_daily_dividend_csv_exports(
                root_dir=root_dir,
                now=current,
                max_state_age_days=int(settings["daily_state_max_age_days"]),
            )
        else:
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
        if settings["reply_to"]:
            message["Reply-To"] = settings["reply_to"]
        if settings["transport"] == "SENDGRID":
            sendgrid_sender(
                message,
                api_key=settings["api_key"],
                sender_name=settings["sender_name"],
                reply_to=settings["reply_to"],
            )
        else:
            smtp_sender(message, password=settings["password"])
        sent.append(frequency)
    return sent


def main() -> int:
    sent = send_scheduled_reports()
    print("Scheduled report email result: " + (", ".join(sent) if sent else "NOT_DUE"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
