"""Publish canonical Dividend income and upcoming-payment evidence.

Reporting-only and paper-only. Realized payments come exclusively from the
existing paper transaction ledger. Upcoming dates are copied only when already
reported by current market evidence; this module never estimates a date.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .dividend_realized_income import build_realized_income_evidence

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
DEFAULT_LOG_PATH = Path("paper_trade_log.csv")
DEFAULT_MARKET_PATH = Path("market_data_snapshot.json")
DEFAULT_PAYMENT_OUTPUT = Path("results/payment_history.json")
DEFAULT_UPCOMING_OUTPUT = Path("results/upcoming_payments.json")


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _market_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("records", "rows", "holdings", "positions", "entries"):
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _first(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


def build_income_payment_evidence(
    *,
    transaction_rows: list[Mapping[str, Any]],
    market_rows: list[Mapping[str, Any]],
    generated_at_utc: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = generated_at_utc or _now_utc()
    realized = build_realized_income_evidence(transaction_rows)
    payments = [dict(item) for item in realized.get("income_events", [])]

    upcoming: list[dict[str, Any]] = []
    for row in market_rows:
        ex_date = _first(row, "next_ex_date", "next_ex_dividend_date", "ex_dividend_date")
        payment_date = _first(row, "next_payment_date", "payment_date")
        if ex_date in (None, "") and payment_date in (None, ""):
            continue
        upcoming.append({
            "symbol": _first(row, "symbol", "ticker", "Ticker"),
            "next_ex_date": ex_date,
            "next_payment_date": payment_date,
            "amount": _first(row, "next_distribution_amount", "dividend_amount"),
            "frequency": _first(row, "distribution_frequency", "dividend_frequency", "frequency"),
            "date_status": "REPORTED",
            "source": "market_data_snapshot.json",
        })

    payment_status = "AVAILABLE" if payments else "AVAILABLE_EMPTY"
    upcoming_status = "AVAILABLE" if upcoming else "NOT_REPORTED"
    common = {
        "schema_version": "1.0",
        "generated_at_utc": generated_at,
        "strategy_id": "DIVIDEND-001",
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
    }
    payment_document = {
        **common,
        "evidence_status": payment_status,
        "record_count": len(payments),
        "records": payments,
        "summary": {
            "gross_distributions": realized.get("gross_distribution_income", 0.0),
            "income_adjustments": realized.get("income_adjustments", 0.0),
            "net_income_received": realized.get("net_income_received", 0.0),
            "income_sleeve_reinvestment": realized.get("income_sleeve_reinvestment", 0.0),
            "growth_sleeve_reinvestment": realized.get("growth_sleeve_reinvestment", 0.0),
        },
        "evidence_source": "paper_trade_log.csv",
        "empty_state_reason": None if payments else "No realized paper distribution events are recorded in the transaction ledger.",
    }
    upcoming_document = {
        **common,
        "evidence_status": upcoming_status,
        "record_count": len(upcoming),
        "records": upcoming,
        "date_policy": "REPORTED_DATES_ONLY_NO_ESTIMATION",
        "evidence_source": "market_data_snapshot.json",
        "empty_state_reason": None if upcoming else "No authoritative upcoming ex-date or payment date is currently reported.",
    }
    return payment_document, upcoming_document


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            json.dump(dict(payload), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def write_income_payment_evidence(
    root_dir: str | Path = ".",
    *,
    log_path: str | Path = DEFAULT_LOG_PATH,
    market_path: str | Path = DEFAULT_MARKET_PATH,
    payment_output: str | Path = DEFAULT_PAYMENT_OUTPUT,
    upcoming_output: str | Path = DEFAULT_UPCOMING_OUTPUT,
) -> dict[str, Any]:
    root = Path(root_dir)

    def under_root(value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else root / path

    payment, upcoming = build_income_payment_evidence(
        transaction_rows=_read_csv(under_root(log_path)),
        market_rows=_market_rows(_read_mapping(under_root(market_path))),
    )
    payment_path = _atomic_write_json(under_root(payment_output), payment)
    upcoming_path = _atomic_write_json(under_root(upcoming_output), upcoming)
    return {
        "payment_history_path": str(payment_path),
        "upcoming_payments_path": str(upcoming_path),
        "payment_record_count": payment["record_count"],
        "upcoming_record_count": upcoming["record_count"],
        "payment_evidence_status": payment["evidence_status"],
        "upcoming_evidence_status": upcoming["evidence_status"],
    }
