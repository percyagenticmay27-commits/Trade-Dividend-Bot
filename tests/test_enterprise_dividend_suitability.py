from __future__ import annotations

import json
from pathlib import Path

import pytest

from enterprise_dividend_suitability import (
    build_suitability_report,
    validate_evidence_catalog,
    validate_mapping_report,
    write_suitability_report,
)


def _mapping_report(mapping_type="INCOME_ETF", underlying="AMD", income="AMDY"):
    return {
        "schema_version": "1.0",
        "strategy_id": "DIVIDEND-001",
        "paper_trade_mode": True,
        "advisory_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "candidates": [{
            "underlying_symbol": underlying,
            "income_symbol": income,
            "mapping_type": mapping_type,
            "mapping_status": "REVIEWED_MAPPING_AVAILABLE",
            "automatic_activation_allowed": False,
        }],
    }


def _evidence(symbol="AMDY", **updates):
    row = {
        "income_symbol": symbol,
        "reviewed": True,
        "evidence_as_of": "2026-08-18",
        "latest_dollar_volume": 5_000_000,
        "total_return_1y_percent": 8.0,
        "expense_ratio_percent": 0.99,
        "latest_distribution_roc_percent": 20.0,
        "fund_age_days": 500,
        "sources": [{"evidence_type": "OFFICIAL_FUND_DATA", "source_url": "https://example.test/fund"}],
    }
    row.update(updates)
    return row


def _catalog(*rows):
    return {"schema_version": "1.0", "strategy_id": "DIVIDEND-001", "vehicles": list(rows)}


def test_missing_reviewed_evidence_fails_closed():
    report = build_suitability_report(
        _mapping_report(), _catalog(), generated_at="2026-08-18T18:00:00Z"
    )
    row = report["candidates"][0]
    assert row["suitability_status"] == "EVIDENCE_REQUIRED"
    assert row["paper_review_allowed"] is False
    assert report["evidence_required_count"] == 1
    assert row["suitability_evidence"] is None


def test_reviewed_income_etf_can_become_paper_review_eligible():
    report = build_suitability_report(
        _mapping_report(), _catalog(_evidence()), generated_at="2026-08-18T18:00:00Z"
    )
    row = report["candidates"][0]
    assert row["suitability_status"] == "ELIGIBLE_FOR_PAPER_REVIEW"
    assert row["suitability_score"] == 100
    assert row["paper_review_allowed"] is True
    assert row["automatic_activation_allowed"] is False
    assert row["suitability_evidence"]["latest_dollar_volume"] == 5_000_000
    assert row["suitability_evidence"]["total_return_1y_percent"] == 8.0
    assert row["suitability_evidence"]["latest_distribution_roc_percent"] == 20.0


def test_high_roc_and_negative_return_remain_watch_only():
    report = build_suitability_report(
        _mapping_report(),
        _catalog(_evidence(latest_distribution_roc_percent=95, total_return_1y_percent=-10)),
        generated_at="2026-08-18T18:00:00Z",
    )
    row = report["candidates"][0]
    assert row["suitability_status"] == "WATCH_ONLY"
    assert row["suitability_score"] == 35
    assert row["paper_review_allowed"] is False


def test_severe_loss_or_illiquidity_is_rejected():
    report = build_suitability_report(
        _mapping_report(),
        _catalog(_evidence(total_return_1y_percent=-45, latest_dollar_volume=100_000)),
        generated_at="2026-08-18T18:00:00Z",
    )
    assert report["candidates"][0]["suitability_status"] == "REJECTED"
    assert report["rejected_count"] == 1


def test_stale_or_incomplete_evidence_requires_refresh():
    stale = build_suitability_report(
        _mapping_report(), _catalog(_evidence(evidence_as_of="2026-06-01")),
        generated_at="2026-08-18T18:00:00Z",
    )
    assert stale["candidates"][0]["suitability_status"] == "EVIDENCE_REQUIRED"

    incomplete = _evidence()
    incomplete["total_return_1y_percent"] = None
    missing = build_suitability_report(
        _mapping_report(), _catalog(incomplete), generated_at="2026-08-18T18:00:00Z"
    )
    assert missing["candidates"][0]["suitability_status"] == "EVIDENCE_REQUIRED"


def test_direct_dividend_equity_uses_dividend_specific_evidence():
    evidence = _evidence(
        "DUK",
        forward_dividend_yield_percent=3.5,
        dividend_cut_last_12m=False,
    )
    evidence.pop("expense_ratio_percent")
    evidence.pop("latest_distribution_roc_percent")
    evidence.pop("fund_age_days")
    report = build_suitability_report(
        _mapping_report("DIRECT_DIVIDEND_EQUITY", "DUK", "DUK"),
        _catalog(evidence),
        generated_at="2026-08-18T18:00:00Z",
    )
    assert report["candidates"][0]["suitability_status"] == "ELIGIBLE_FOR_PAPER_REVIEW"



def test_low_yield_direct_dividend_equity_remains_watch_only():
    evidence = _evidence(
        "AMAT",
        forward_dividend_yield_percent=0.4,
        dividend_cut_last_12m=False,
    )
    evidence.pop("expense_ratio_percent")
    evidence.pop("latest_distribution_roc_percent")
    evidence.pop("fund_age_days")
    report = build_suitability_report(
        _mapping_report("DIRECT_DIVIDEND_EQUITY", "AMAT", "AMAT"),
        _catalog(evidence),
        generated_at="2026-08-18T18:00:00Z",
    )
    row = report["candidates"][0]
    assert row["suitability_status"] == "WATCH_ONLY"
    assert row["suitability_score"] == 65
    assert row["paper_review_allowed"] is False
    assert "below 1.00%" in row["decision_reasons"][0]


def test_unreviewed_or_insecure_evidence_is_rejected():
    row = _evidence()
    row["reviewed"] = False
    with pytest.raises(ValueError, match="must be reviewed"):
        validate_evidence_catalog(_catalog(row))
    row = _evidence()
    row["sources"][0]["source_url"] = "http://example.test/fund"
    with pytest.raises(ValueError, match="HTTPS"):
        validate_evidence_catalog(_catalog(row))


def test_mapping_execution_lock_failure_is_rejected():
    mapping = _mapping_report()
    mapping["order_placement_enabled"] = True
    with pytest.raises(ValueError, match="execution locks"):
        validate_mapping_report(mapping)


def test_written_report_preserves_all_locks(tmp_path: Path):
    mapping = tmp_path / "mapping.json"
    evidence = tmp_path / "evidence.json"
    output = tmp_path / "report.json"
    mapping.write_text(json.dumps(_mapping_report()), encoding="utf-8")
    evidence.write_text(json.dumps(_catalog()), encoding="utf-8")
    report = write_suitability_report(mapping, evidence, output)
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert report["paper_trade_mode"] is True
    assert report["advisory_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["order_placement_enabled"] is False
    assert report["capital_movement_enabled"] is False
    assert report["automatic_activation_allowed"] is False
