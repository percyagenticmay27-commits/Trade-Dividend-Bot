"""Convert required Dividend Markdown reports to executive CSV evidence."""
from __future__ import annotations

import csv
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.dividend_bot.executive_reporting_framework import executive_framework_rows

MODULE_NAME = "daily_markdown_report_csv"
MODULE_VERSION = "2.0.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

REPORT_EXPORTS = (
    (Path("daily_paper_report.md"), "daily_paper_report.csv"),
    (Path("daily_change_summary.md"), "daily_change_summary.csv"),
    (Path("strategy_health_report.md"), "strategy_health_report.csv"),
    (Path("live_readiness_report.md"), "live_readiness_report.csv"),
)

CSV_FIELDS = [
    "report_section",
    "field",
    "value",
    "report_text",
    "source_line",
    "paper_trade_mode",
]


def _atomic_write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=str(path.parent), text=True
    )
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _strip_markdown(text: str) -> str:
    value = text.strip()
    value = re.sub(r"^[-*+]\s+", "", value)
    value = re.sub(r"^\d+[.)]\s+", "", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    return value.strip()


def _framework_csv_rows(
    source: Path,
    *,
    as_of_date: date,
    generated_at: datetime,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in executive_framework_rows(
        source_name=source.name,
        trading_date=as_of_date,
        generated_at=generated_at,
    ):
        rows.append(
            {
                "report_section": item["section"],
                "field": item["field"],
                "value": item["value"],
                "report_text": "",
                "source_line": "",
                "paper_trade_mode": True,
            }
        )
    return rows


def markdown_rows(
    source: Path,
    *,
    as_of_date: date,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    if not source.is_file():
        raise RuntimeError(f"Required daily Dividend report is missing: {source}")
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Required daily Dividend report is unreadable: {source}") from exc

    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    rows = _framework_csv_rows(source, as_of_date=as_of_date, generated_at=generated)
    section = "Report Details"
    in_code_block = False

    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        field = ""
        value = ""
        text = _strip_markdown(stripped)

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading and not in_code_block:
            section = _strip_markdown(heading.group(2))
            field = "Section"
            value = section
            text = ""
        elif not in_code_block and ":" in text:
            possible_field, possible_value = text.split(":", 1)
            if possible_field.strip() and possible_value.strip():
                field = possible_field.strip()
                value = possible_value.strip()
                text = ""

        rows.append(
            {
                "report_section": section,
                "field": field,
                "value": value,
                "report_text": text,
                "source_line": line_number,
                "paper_trade_mode": True,
            }
        )

    content_rows = [row for row in rows if row["source_line"] != ""]
    if not content_rows:
        raise RuntimeError(f"Required daily Dividend report is empty: {source}")
    return rows


def generate_markdown_report_csvs(
    *,
    root_dir: str | Path,
    output_dir: str | Path,
    as_of_date: date,
    generated_at: datetime | None = None,
) -> list[Path]:
    root = Path(root_dir)
    destination = root / Path(output_dir)
    generated = generated_at or datetime.now(timezone.utc)
    outputs: list[Path] = []
    for source_relative, output_name in REPORT_EXPORTS:
        source = root / source_relative
        output = destination / output_name
        _atomic_write_csv(
            output,
            markdown_rows(
                source,
                as_of_date=as_of_date,
                generated_at=generated,
            ),
        )
        outputs.append(output)
    return outputs
