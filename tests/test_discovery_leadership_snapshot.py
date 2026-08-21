from __future__ import annotations

from datetime import date, timedelta

from src.dividend_bot.discovery_leadership_snapshot import (
    calculate_relative_leadership_from_snapshot,
    enrich_swing_discovery_bucket_from_snapshot,
)


def _dates(count=160, start=date(2026, 1, 2)):
    current = start
    result = []
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def _history(start, end, count=160):
    days = _dates(count)
    step = (end - start) / (count - 1)
    return {
        "data_source": "CACHE_FRESH",
        "is_stale": False,
        "rows": [
            {
                "date": day.isoformat() + "T00:00:00-04:00",
                "close": start + step * index,
                "adj_close": start + step * index,
                "volume": 10_000_000 + index,
            }
            for index, day in enumerate(days)
        ],
    }


def _record(symbol, start, end, *, sector="Technology", industry="Semiconductors", stale=False):
    return {
        "symbol": symbol,
        "sector": sector,
        "industry": industry,
        "history_source": "CACHE_FRESH",
        "is_stale": stale,
        "history": _history(start, end),
    }


def _snapshot(*records):
    return {
        "schema_version": "1.0",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only_market_data": True,
        "records": list(records),
    }


def _bucket(*symbols):
    return {
        "schema_version": "1.0",
        "strategy_id": "SWING-001",
        "candidates": [
            {
                "underlying_symbol": symbol,
                "discovery_status": "RISING",
                "weekly_lifecycle_status": "RISING",
                "themes": [],
                "evidence_sources": [],
            }
            for symbol in symbols
        ],
    }


def _report(*symbols):
    return {
        "generated_at": "2026-08-21T12:00:00Z",
        "candidates": [
            {"underlying_symbol": symbol, "source_confluence": {"level": "CONFIRMED"}}
            for symbol in symbols
        ],
    }


def test_snapshot_relative_leadership_uses_existing_history_contract():
    snapshot = _snapshot(
        _record("SPY", 100, 110),
        _record("AAA", 100, 180),
    )
    result = calculate_relative_leadership_from_snapshot(snapshot, "AAA", observed_on=date(2026, 8, 21))
    assert result["evidence_status"] == "AVAILABLE"
    assert result["evidence_source"] == "AI_CIO_MARKET_DATA_SNAPSHOT"
    assert result["leadership_classification"] in {"LEADER", "EXCEPTIONAL_LEADER"}
    assert result["evaluated_horizons"] == 4
    assert result["stock_history_source"] == "CACHE_FRESH"


def test_snapshot_missing_spy_fails_closed_without_fabrication():
    snapshot = _snapshot(_record("AAA", 100, 180))
    result = calculate_relative_leadership_from_snapshot(snapshot, "AAA")
    assert result["evidence_status"] == "MISSING"
    assert result["leadership_score"] is None
    assert "BENCHMARK_SNAPSHOT_RECORD_MISSING" in result["warnings"]


def test_snapshot_stale_market_data_is_disclosed():
    snapshot = _snapshot(
        _record("SPY", 100, 110),
        _record("AAA", 100, 180, stale=True),
    )
    result = calculate_relative_leadership_from_snapshot(snapshot, "AAA")
    assert result["evidence_status"] == "AVAILABLE"
    assert "STOCK_MARKET_DATA_STALE" in result["warnings"]


def test_snapshot_sector_and_industry_come_from_market_records():
    snapshot = _snapshot(
        _record("SPY", 100, 110, sector="ETF", industry="Index"),
        _record("AAA", 100, 200),
        _record("BBB", 100, 190),
    )
    result = enrich_swing_discovery_bucket_from_snapshot(
        _bucket("AAA", "BBB"),
        _report("AAA", "BBB"),
        [{"underlying_symbol": "AAA"}, {"underlying_symbol": "BBB"}],
        snapshot,
    )
    aaa = next(row for row in result["candidates"] if row["underlying_symbol"] == "AAA")
    assert aaa["sector_leadership"]["name"] == "Technology"
    assert aaa["industry_leadership"]["name"] == "Semiconductors"
    assert aaa["industry_leadership"]["classification"] == "LEADING"
    assert "LEADING_INDUSTRY" in aaa["discovery_reasons"]


def test_snapshot_enrichment_preserves_swing_contract_and_has_no_trade_fields():
    snapshot = _snapshot(
        _record("SPY", 100, 110),
        _record("AAA", 100, 180),
    )
    result = enrich_swing_discovery_bucket_from_snapshot(
        _bucket("AAA"),
        _report("AAA"),
        [{"underlying_symbol": "AAA"}],
        snapshot,
    )
    assert result["schema_version"] == "1.0"
    assert result["strategy_id"] == "SWING-001"
    candidate = result["candidates"][0]
    assert candidate["underlying_symbol"] == "AAA"
    assert candidate["discovery_status"] == "RISING"
    assert "relative_leadership" in candidate
    assert "entry_score" not in candidate
    assert "opportunity_quality" not in candidate
    assert "buy" not in candidate


def test_unknown_snapshot_metadata_does_not_create_fake_peer_groups():
    snapshot = _snapshot(
        _record("SPY", 100, 110, sector="ETF", industry="Index"),
        _record("AAA", 100, 180, sector="UNKNOWN", industry="UNKNOWN"),
    )
    result = enrich_swing_discovery_bucket_from_snapshot(
        _bucket("AAA"),
        _report("AAA"),
        [{"underlying_symbol": "AAA"}],
        snapshot,
    )
    candidate = result["candidates"][0]
    assert candidate["sector_leadership"]["evidence_status"] == "MISSING"
    assert candidate["industry_leadership"]["evidence_status"] == "MISSING"
