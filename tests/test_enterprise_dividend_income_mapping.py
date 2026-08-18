from __future__ import annotations

import json
from pathlib import Path

import pytest

from enterprise_dividend_income_mapping import (
    build_income_mapping_report,
    validate_mapping_catalog,
    write_income_mapping_report,
)


def _bucket(*symbols: str):
    return {
        "schema_version": "1.0",
        "strategy_id": "DIVIDEND-001",
        "paper_trade_mode": True,
        "advisory_only": True,
        "candidates": [
            {
                "underlying_symbol": symbol,
                "discovery_status": "NEW",
                "requires_dividend_income_mapping": True,
                "promotion_authority": "DIVIDEND-001",
            }
            for symbol in symbols
        ],
    }


def _mapping(underlying: str = "HD", income: str = "SCHD"):
    return {
        "underlying_symbol": underlying,
        "income_symbol": income,
        "mapping_type": "INCOME_ETF",
        "status": "REVIEWED",
        "reviewed": True,
        "automatic_activation_allowed": False,
        "mapping_evidence": [
            {
                "evidence_type": "FUND_HOLDINGS",
                "source_url": "https://example.test/fund-holdings",
                "as_of": "2026-08-18",
            },
            {
                "evidence_type": "DISTRIBUTION_HISTORY",
                "source_url": "https://example.test/distributions",
                "as_of": "2026-08-18",
            },
        ],
    }


def test_unknown_discovery_symbols_fail_closed_to_research_required():
    report = build_income_mapping_report(
        _bucket("AMAT", "HD"),
        {"schema_version": "1.0", "strategy_id": "DIVIDEND-001", "mappings": []},
        generated_at="2026-08-18T16:00:00Z",
    )
    assert report["reviewed_mapping_count"] == 0
    assert report["research_required_count"] == 2
    assert all(row["income_symbol"] is None for row in report["candidates"])
    assert all(row["automatic_activation_allowed"] is False for row in report["candidates"])


def test_only_reviewed_evidence_backed_mapping_is_projected():
    report = build_income_mapping_report(
        _bucket("HD", "SMCI"),
        {
            "schema_version": "1.0",
            "strategy_id": "DIVIDEND-001",
            "mappings": [_mapping()],
        },
        generated_at="2026-08-18T16:00:00Z",
    )
    rows = {row["underlying_symbol"]: row for row in report["candidates"]}
    assert rows["HD"]["mapping_status"] == "REVIEWED_MAPPING_AVAILABLE"
    assert rows["HD"]["income_symbol"] == "SCHD"
    assert len(rows["HD"]["mapping_evidence"]) == 2
    assert rows["SMCI"]["mapping_status"] == "RESEARCH_REQUIRED"
    assert rows["SMCI"]["income_symbol"] is None


def test_unreviewed_or_unsupported_mapping_fails_closed():
    unreviewed = _mapping()
    unreviewed["reviewed"] = False
    with pytest.raises(ValueError, match="explicitly reviewed"):
        validate_mapping_catalog(
            {"schema_version": "1.0", "strategy_id": "DIVIDEND-001", "mappings": [unreviewed]}
        )

    unsupported = _mapping()
    unsupported["mapping_type"] = "LEVERAGED_ETF"
    with pytest.raises(ValueError, match="mapping_type"):
        validate_mapping_catalog(
            {"schema_version": "1.0", "strategy_id": "DIVIDEND-001", "mappings": [unsupported]}
        )


def test_mapping_requires_https_evidence_and_never_activates():
    row = _mapping()
    row["mapping_evidence"][0]["source_url"] = "http://example.test/not-approved"
    with pytest.raises(ValueError, match="HTTPS"):
        validate_mapping_catalog(
            {"schema_version": "1.0", "strategy_id": "DIVIDEND-001", "mappings": [row]}
        )


def test_output_preserves_all_execution_locks(tmp_path: Path):
    discovery = tmp_path / "bucket.json"
    catalog = tmp_path / "catalog.json"
    output = tmp_path / "report.json"
    discovery.write_text(json.dumps(_bucket("HD")), encoding="utf-8")
    catalog.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "strategy_id": "DIVIDEND-001",
                "mappings": [_mapping()],
            }
        ),
        encoding="utf-8",
    )
    report = write_income_mapping_report(discovery, catalog, output)
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["paper_trade_mode"] is True
    assert report["advisory_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["order_placement_enabled"] is False
    assert report["capital_movement_enabled"] is False
    assert report["automatic_activation_allowed"] is False

def test_production_catalog_contains_only_reviewed_direct_dividend_mappings():
    catalog_path = Path("configs/dividend_discovery_income_mappings.json")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    mappings = validate_mapping_catalog(payload)
    assert set(mappings) == {"AMAT", "HD", "KDP", "WNC"}
    assert all(row["income_symbol"] == symbol for symbol, row in mappings.items())
    assert all(row["mapping_type"] == "DIRECT_DIVIDEND_EQUITY" for row in mappings.values())
    assert all(row["automatic_activation_allowed"] is False for row in mappings.values())
    assert all(row["mapping_evidence"] for row in mappings.values())

