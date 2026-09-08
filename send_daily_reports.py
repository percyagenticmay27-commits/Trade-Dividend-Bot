"""Email the four PAPER ONLY daily decision reports as CSV attachments."""

from __future__ import annotations

import csv
import json
import os
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from shared.notifications.sendgrid_email import send_email
from src.dividend_bot.daily_markdown_report_csv import generate_markdown_report_csvs


load_dotenv(".env")
SENDER = os.getenv("SENDGRID_FROM_EMAIL", "prproducts3000@gmail.com")
RECIPIENT = os.getenv("REPORT_RECIPIENT", "percyagenticmay27@gmail.com")
STATE_PATH = Path("paper_state.json")
DELIVERY_LOG_PATH = Path("email_delivery_log.csv")
CSV_OUTPUT_DIR = Path("results/daily_decision_report_csv")
SOURCE_REPORTS = (
    Path("daily_paper_report.md"),
    Path("daily_change_summary.md"),
    Path("strategy_health_report.md"),
    Path("live_readiness_report.md"),
)
EXPECTED_CSV_NAMES = (
    "daily_paper_report.csv",
    "daily_change_summary.csv",
    "strategy_health_report.csv",
    "live_readiness_report.csv",
)
DELIVERY_COLUMNS = [
    "Sent_At",
    "Report_Date",
    "Sender",
    "Recipient",
    "Subject",
    "Attachments",
    "Status",
]


def report_date(state_path: Path = STATE_PATH) -> str:
    if not state_path.exists():
        raise FileNotFoundError(f"Paper state not found: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    return str(state["as_of_date"])


def build_csv_attachments(
    *,
    root_dir: str | Path,
    current_report_date: str,
    output_dir: str | Path = CSV_OUTPUT_DIR,
) -> list[Path]:
    """Convert the exact four authoritative Markdown decision reports to CSV."""
    try:
        as_of = date.fromisoformat(current_report_date[:10])
    except ValueError as exc:
        raise RuntimeError(f"Invalid paper-state report date: {current_report_date}") from exc

    outputs = generate_markdown_report_csvs(
        root_dir=root_dir,
        output_dir=output_dir,
        as_of_date=as_of,
    )
    names = tuple(path.name for path in outputs)
    if names != EXPECTED_CSV_NAMES:
        raise RuntimeError(
            "Unexpected daily decision CSV attachment set: " + ", ".join(names)
        )
    if not all(path.is_file() and path.stat().st_size > 0 for path in outputs):
        raise RuntimeError("One or more daily decision CSV attachments were not generated")
    return outputs


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
    unexpected = [path.name for path in attachments if path.suffix.lower() != ".csv"]
    if unexpected:
        raise ValueError(
            "Daily decision email attachments must be CSV files: " + ", ".join(unexpected)
        )

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"PAPER ONLY ETF Daily Decision Reports - {current_report_date}"
    message.set_content(
        "PAPER ONLY - NO REAL TRADES EXECUTED\n\n"
        f"Attached are the four daily ETF decision reports through {current_report_date}, "
        "converted from the authoritative Markdown reports to CSV format.\n\n"
        "Source reports:\n"
        + "\n".join(f"- {path.name}" for path in SOURCE_REPORTS)
        + "\n\nCSV attachments:\n"
        + "\n".join(f"- {path.name}" for path in attachments)
        + "\n"
    )
    for path in attachments:
        message.add_attachment(
            path.read_bytes(),
            maintype="text",
            subtype="csv",
            filename=path.name,
        )
    return message


def append_delivery_log(
    path: Path,
    current_report_date: str,
    message: EmailMessage,
    attachments: list[Path],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    smtp_factory=None,
    *,
    root_dir: str | Path = ".",
    email_sender: Callable[..., object] = send_email,
) -> str:
    """Send the existing daily decision email with four generated CSV reports."""
    del password, smtp_factory  # Retained for compatibility with older callers.
    root = Path(root_dir)
    resolved_state = state_path if state_path.is_absolute() else root / state_path
    resolved_log = delivery_log if delivery_log.is_absolute() else root / delivery_log
    current_report_date = report_date(resolved_state)
    if already_sent(resolved_log, current_report_date, recipient):
        return "SKIPPED_ALREADY_SENT"

    csv_attachments = attachments or build_csv_attachments(
        root_dir=root,
        current_report_date=current_report_date,
    )
    message = build_message(
        current_report_date,
        csv_attachments,
        sender=sender,
        recipient=recipient,
    )
    body_part = message.get_body(preferencelist=("plain",))
    body_text = body_part.get_content() if body_part else str(message)

    email_sender(
        subject=str(message["Subject"]),
        body=body_text,
        recipient=recipient,
        attachments=csv_attachments,
    )
    append_delivery_log(
        resolved_log,
        current_report_date,
        message,
        csv_attachments,
    )
    return "SENT"


def main() -> int:
    result = send_daily_reports()
    print(f"Daily report email: {result}")
    print(f"Sender: {SENDER}")
    print(f"Recipient: {RECIPIENT}")
    print("Attachments: " + ", ".join(EXPECTED_CSV_NAMES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
