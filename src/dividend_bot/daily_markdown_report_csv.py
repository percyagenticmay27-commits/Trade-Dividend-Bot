"""Convert required Dividend Markdown reports to structured daily CSV evidence."""
from __future__ import annotations

import csv
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

MODULE_NAME = "daily_markdown_report_csv"
MODULE_VERSION = "1.0.0"
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
    "as_of_date",
    "source_file",
    "section",
    "row_type",
    "label",
    "value",
    "text",
    "line_number",
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


def markdown_rows(source: Path, *, as_of_date: date) -> list[dict[str, Any]]:
    if not source.is_file():
        raise RuntimeError(f"Required daily Dividend report is missing: {source}")
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Required daily Dividend report is unreadable: {source}") from exc

    rows: list[dict[str, Any]] = []
    section = ""
    in_code_block = False
    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        row_type = "code" if in_code_block else "text"
        label = ""
        value = ""
        text = stripped

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading and not in_code_block:
            section = _strip_markdown(heading.group(2))
            row_type = "heading"
            text = section
        elif re.match(r"^[-*+]\s+", stripped) and not in_code_block:
            row_type = "bullet"
            text = _strip_markdown(stripped)
        elif re.match(r"^\d+[.)]\s+", stripped) and not in_code_block:
            row_type = "numbered_item"
            text = _strip_markdown(stripped)

        normalized = _strip_markdown(text)
        if not in_code_block and ":" in normalized:
            possible_label, possible_value = normalized.split(":", 1)
            if possible_label.strip() and possible_value.strip():
                label = possible_label.strip()
                value = possible_value.strip()
                if row_type == "text":
                    row_type = "key_value"

        rows.append(
            {
                "as_of_date": as_of_date.isoformat(),
                "source_file": source.name,
                "section": section,
                "row_type": row_type,
                "label": label,
                "value": value,
                "text": normalized,
                "line_number": line_number,
                "paper_trade_mode": True,
            }
        )

    if not rows:
        raise RuntimeError(f"Required daily Dividend report is empty: {source}")
    return rows


def generate_markdown_report_csvs(
    *, root_dir: str | Path, output_dir: str | Path, as_of_date: date
) -> list[Path]:
    root = Path(root_dir)
    destination = root / Path(output_dir)
    outputs: list[Path] = []
    for source_relative, output_name in REPORT_EXPORTS:
        source = root / source_relative
        output = destination / output_name
        _atomic_write_csv(output, markdown_rows(source, as_of_date=as_of_date))
        outputs.append(output)
    return outputs
