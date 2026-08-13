from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_income_payment_evidence import (
    build_income_payment_evidence,
    write_income_payment_evidence,
)


def test_builds_payment_history_only_from_recorded_ledger_events() -> None:
    payment, upcoming = build_income_payment_evidence(
        generated_at_utc="2026-08-12T00:00:00Z",
        transaction_rows=[
            {
                "Date": "2026-08-10",
                "Pair": "AMDW / AMDL",
                "Ticker": "AMDW",
                "Action": "PAPER_DIVIDEND_RECEIVED",
                "Paper_Value": "3.20",
                "Reason": "Income ETF dividend split 50/50 between A and B",
            },
            {
                "Date": "2026-08-11",
                "Ticker": "AMDW",
                "Action": "PAPER_BUY_FROM_SGOV",
                "Paper_Value": "50.00",
            },
        ],
        market_rows=[],
    )

    assert payment["evidence_status"] == "AVAILABLE"
    assert payment["record_count"] == 1
    assert payment["summary"]["net_income_received"] == 3.20
    assert payment["summary"]["income_sleeve_reinvestment"] == 1.60
    assert payment["summary"]["growth_sleeve_reinvestment"] == 1.60
    assert payment["records"][0]["symbol"] == "AMDW"
    assert upcoming["evidence_status"] == "NOT_REPORTED"
    assert upcoming["records"] == []


def test_empty_ledger_is_available_empty_not_missing_or_fabricated() -> None:
    payment, upcoming = build_income_payment_evidence(
        generated_at_utc="2026-08-12T00:00:00Z",
        transaction_rows=[],
        market_rows=[],
    )

    assert payment["evidence_status"] == "AVAILABLE_EMPTY"
    assert payment["record_count"] == 0
    assert payment["summary"]["net_income_received"] == 0.0
    assert "No realized paper distribution events" in payment["empty_state_reason"]
    assert upcoming["evidence_status"] == "NOT_REPORTED"
    assert upcoming["record_count"] == 0


def test_upcoming_payment_uses_only_reported_dates() -> None:
    _, upcoming = build_income_payment_evidence(
        generated_at_utc="2026-08-12T00:00:00Z",
        transaction_rows=[],
        market_rows=[
            {
                "symbol": "AMDW",
                "next_ex_date": "2026-08-17",
                "distribution_frequency": "WEEKLY",
            },
            {
                "symbol": "AMDL",
                "distribution_frequency": "UNKNOWN",
            },
        ],
    )

    assert upcoming["evidence_status"] == "AVAILABLE"
    assert upcoming["record_count"] == 1
    assert upcoming["records"][0]["symbol"] == "AMDW"
    assert upcoming["records"][0]["next_ex_date"] == "2026-08-17"
    assert upcoming["date_policy"] == "REPORTED_DATES_ONLY_NO_ESTIMATION"


def test_writer_publishes_canonical_json_without_touching_source(tmp_path: Path) -> None:
    log = tmp_path / "paper_trade_log.csv"
    log.write_text(
        "Date,Pair,Ticker,Action,Paper_Value,Reason\n"
        "2026-08-10,AMDW / AMDL,AMDW,PAPER_DIVIDEND_RECEIVED,2.00,recorded\n",
        encoding="utf-8",
    )
    before = log.read_bytes()

    report = write_income_payment_evidence(tmp_path)

    assert log.read_bytes() == before
    payment_path = Path(report["payment_history_path"])
    upcoming_path = Path(report["upcoming_payments_path"])
    assert payment_path == tmp_path / "results/payment_history.json"
    assert upcoming_path == tmp_path / "results/upcoming_payments.json"
    payment = json.loads(payment_path.read_text(encoding="utf-8"))
    upcoming = json.loads(upcoming_path.read_text(encoding="utf-8"))
    assert payment["record_count"] == 1
    assert upcoming["evidence_status"] == "NOT_REPORTED"
    assert not list((tmp_path / "results").glob("*.tmp"))
