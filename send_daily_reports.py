"""Email the four PAPER ONLY daily decision reports through SendGrid REST API."""

from __future__ import annotations

import csv
import json
import os
import ssl
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv
from shared.notifications.sendgrid_email import send_email


load_dotenv(".env")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SENDER = os.getenv("SENDGRID_FROM_EMAIL", "prproducts3000@gmail.com")
RECIPIENT = os.getenv("REPORT_RECIPIENT", "percyagenticmay27@gmail.com")
PASSWORD_ENV = "GMAIL_APP_PASSWORD"
STATE_PATH = Path("paper_state.json")
DELIVERY_LOG_PATH = Path("email_delivery_log.csv")
ATTACHMENTS = [
    Path("daily_paper_report.md"),
    Path("daily_change_summary.md"),
    Path("strategy_health_report.md"),
    Path("live_readiness_report.md"),
]
DELIVERY_COLUMNS = [
    "Sent_At",
    "Report_Date",
    "Sender",
    "Recipient",
    "Subject",
    "Attachments",
    "Status",
]


class SMTPConnection(Protocol):
    def __enter__(self): ...
    def __exit__(self, exc_type, exc, traceback): ...
    def login(self, user: str, password: str): ...
    def send_message(self, message: EmailMessage): ...


def gmail_connection() -> SMTPConnection:
    context = ssl.create_default_context()
    return smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30)


def configured_app_password(explicit_password: str | None = None) -> str | None:
    """Load the app password from the process or persistent Windows user env."""
    if explicit_password:
        return explicit_password
    process_value = os.environ.get(PASSWORD_ENV)
    if process_value:
        return process_value
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, PASSWORD_ENV)
                return str(value) if value else None
        except FileNotFoundError:
            return None
    return None


def report_date(state_path: Path = STATE_PATH) -> str:
    if not state_path.exists():
        raise FileNotFoundError(f"Paper state not found: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    return str(state["as_of_date"])


def validate_attachments(attachments: list[Path]) -> None:
    missing = [str(path) for path in attachments if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Required daily email attachments are missing: " + ", ".join(missing)
        )
    unexpected = [path for path in attachments if path.suffix.lower() != ".md"]
    if unexpected:
        raise ValueError("Daily email attachments must be Markdown reports only")


def already_sent(
    delivery_log: Path,
    current_report_date: str,
    recipient: str,
) -> bool:
    if not delivery_log.exists():
        return False
    with delivery_log.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return any(
            row["Report_Date"] == current_report_date
            and row["Recipient"] == recipient
            and row["Status"] == "SENT"
            for row in rows
        )


def build_message(
    current_report_date: str,
    attachments: list[Path],
    sender: str = SENDER,
    recipient: str = RECIPIENT,
) -> EmailMessage:
    validate_attachments(attachments)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = (
        f"PAPER ONLY ETF Daily Decision Reports - {current_report_date}"
    )
    message.set_content(
        "PAPER ONLY - NO REAL TRADES EXECUTED\n\n"
        f"Attached are the four daily decision reports through {current_report_date}.\n\n"
        "Attached:\n"
        + "\n".join(f"- {path.name}" for path in attachments)
        + "\n\nCSV, state, and log audit files remain local and are not attached.\n"
    )
    for path in attachments:
        message.add_attachment(
            path.read_text(encoding="utf-8"),
            subtype="markdown",
            filename=path.name,
        )
    return message


def append_delivery_log(
    path: Path,
    current_report_date: str,
    message: EmailMessage,
    attachments: list[Path],
) -> None:
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DELIVERY_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "Sent_At": datetime.now().astimezone().isoformat(timespec="seconds"),
                "Report_Date": current_report_date,
                "Sender": message["From"],
                "Recipient": message["To"],
                "Subject": message["Subject"],
                "Attachments": ";".join(path.name for path in attachments),
                "Status": "SENT",
            }
        )


def send_daily_reports(
    password: str | None = None,
    sender: str = SENDER,
    recipient: str = RECIPIENT,
    attachments: list[Path] | None = None,
    state_path: Path = STATE_PATH,
    delivery_log: Path = DELIVERY_LOG_PATH,
    smtp_factory=gmail_connection,
) -> str:
    attachments = attachments or ATTACHMENTS
    current_report_date = report_date(state_path)
    if already_sent(delivery_log, current_report_date, recipient):
        return "SKIPPED_ALREADY_SENT"

    message = build_message(
    current_report_date,
    attachments,
    sender=sender,
    recipient=recipient,
)

    body_part = message.get_body(preferencelist=("plain",))
    body_text = body_part.get_content() if body_part else str(message)

    send_email(
        subject=str(message["Subject"]),
        body=body_text,
        recipient=recipient,
        attachments=attachments,
    )

    append_delivery_log(
        delivery_log,
        current_report_date,
        message,
        attachments,
    )

    return "SENT"


def main() -> int:
    result = send_daily_reports()
    print(f"Daily report email: {result}")
    print(f"Sender: {SENDER}")
    print(f"Recipient: {RECIPIENT}")
    print("Attachments: " + ", ".join(path.name for path in ATTACHMENTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
