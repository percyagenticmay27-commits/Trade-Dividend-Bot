from __future__ import annotations

import csv
from datetime import date, timedelta

from src.dividend_bot.discovery_leadership import (
    calculate_relative_leadership,
    enrich_swing_discovery_bucket,
    has_trapper_2x_spy_evidence,
)


def _write_history(root, symbol, closes, *, start=date(2026, 1, 2)):
    path = root / f"{symbol}.csv"
    current = start
    rows = []
    for close in closes:
        while current.weekday() >= 5:
            current += timedelta(days=1)
        rows.append((current.isoformat(), close))
        current += timedelta(days=1)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "Close"])
        writer.writerows(rows)


def _series(start, end, count=160):
    step = (end - start) / (count - 1)
    return [start + step * index for index in range(count)]


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


def _report(*rows):
    return {
        "generated_at": "2026-08-21T12:00:00Z",
        "candidates": list(rows),
    }


def test_substantial_outperformance_is_leader(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 110))
    _write_history(tmp_path, "AAA", _series(100, 150))
    result = calculate_relative_leadership(tmp_path, "AAA", observed_on=date(2026, 8, 21))
    assert result["evidence_status"] == "AVAILABLE"
    assert result["leadership_classification"] in {"LEADER", "EXCEPTIONAL_LEADER"}
    assert result["leadership_persistence"] >= 0.5


def test_market_matching_stock_is_market_performer(tmp_path):
    values = _series(100, 110)
    _write_history(tmp_path, "SPY", values)
    _write_history(tmp_path, "AAA", values)
    result = calculate_relative_leadership(tmp_path, "AAA")
    assert result["leadership_classification"] == "MARKET_PERFORMER"


def test_underperforming_stock_is_weak(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 120))
    _write_history(tmp_path, "AAA", _series(100, 90))
    result = calculate_relative_leadership(tmp_path, "AAA")
    assert result["leadership_classification"] == "WEAK"


def test_negative_spy_period_does_not_use_misleading_multiple(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 85))
    _write_history(tmp_path, "AAA", _series(100, 105))
    result = calculate_relative_leadership(tmp_path, "AAA")
    available = [row for row in result["horizons"].values() if row.get("evidence_status") == "AVAILABLE"]
    assert available
    assert all(row["relative_multiple"] is None for row in available)
    assert all(row["trapper_2x_spy_evidence"] is False for row in available)
    assert any("MULTIPLE_NOT_MEANINGFUL" in row.get("warning", "") for row in available)


def test_near_zero_spy_period_does_not_divide_by_zero(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 100.2))
    _write_history(tmp_path, "AAA", _series(100, 120))
    result = calculate_relative_leadership(tmp_path, "AAA")
    assert result["evidence_status"] == "AVAILABLE"
    assert all(
        row.get("relative_multiple") is None
        for row in result["horizons"].values()
        if row.get("evidence_status") == "AVAILABLE"
    )


def test_missing_benchmark_is_explicit(tmp_path):
    _write_history(tmp_path, "AAA", _series(100, 120))
    result = calculate_relative_leadership(tmp_path, "AAA")
    assert result["evidence_status"] == "MISSING"
    assert "BENCHMARK_HISTORY_MISSING" in result["warnings"]
    assert result["leadership_score"] is None


def test_missing_stock_history_is_explicit(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 120))
    result = calculate_relative_leadership(tmp_path, "AAA")
    assert result["evidence_status"] == "MISSING"
    assert "STOCK_HISTORY_MISSING" in result["warnings"]


def test_missing_sector_and_industry_do_not_reject_candidate(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 110))
    _write_history(tmp_path, "AAA", _series(100, 140))
    result = enrich_swing_discovery_bucket(
        _bucket("AAA"),
        _report({"underlying_symbol": "AAA", "themes": [], "source_confluence": {"level": "NONE"}}),
        [{"underlying_symbol": "AAA"}],
        history_dir=tmp_path,
    )
    candidate = result["candidates"][0]
    assert candidate["sector_leadership"]["evidence_status"] == "MISSING"
    assert candidate["industry_leadership"]["evidence_status"] == "MISSING"
    assert candidate["underlying_symbol"] == "AAA"


def test_leading_stock_in_leading_industry_gets_reason(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 110))
    # Use peers that are leaders across the short and long horizons so the
    # peer-average industry score genuinely reaches the LEADING band.
    _write_history(tmp_path, "AAA", _series(100, 200))
    _write_history(tmp_path, "BBB", _series(100, 190))
    weekly = _report(
        {"underlying_symbol": "AAA", "sector": "Technology", "source_confluence": {"level": "CONFIRMED"}},
        {"underlying_symbol": "BBB", "sector": "Technology", "source_confluence": {"level": "CONFIRMED"}},
    )
    observations = [
        {"underlying_symbol": "AAA", "industry": "Semiconductors"},
        {"underlying_symbol": "BBB", "industry": "Semiconductors"},
    ]
    result = enrich_swing_discovery_bucket(_bucket("AAA", "BBB"), weekly, observations, history_dir=tmp_path)
    aaa = next(row for row in result["candidates"] if row["underlying_symbol"] == "AAA")
    assert aaa["industry_leadership"]["classification"] == "LEADING"
    assert "LEADING_INDUSTRY" in aaa["discovery_reasons"]


def test_leading_stock_can_be_in_weak_industry(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 110))
    _write_history(tmp_path, "AAA", _series(100, 150))
    for symbol, end in (("BBB", 70), ("CCC", 75), ("DDD", 80)):
        _write_history(tmp_path, symbol, _series(100, end))
    symbols = ("AAA", "BBB", "CCC", "DDD")
    weekly = _report(*[
        {"underlying_symbol": symbol, "sector": "Mixed", "source_confluence": {"level": "NONE"}}
        for symbol in symbols
    ])
    observations = [{"underlying_symbol": symbol, "industry": "WeakGroup"} for symbol in symbols]
    result = enrich_swing_discovery_bucket(_bucket(*symbols), weekly, observations, history_dir=tmp_path)
    aaa = next(row for row in result["candidates"] if row["underlying_symbol"] == "AAA")
    assert aaa["relative_leadership"]["leadership_classification"] in {"LEADER", "EXCEPTIONAL_LEADER"}
    assert aaa["industry_leadership"]["classification"] in {"WEAK", "MARKET_PERFORMER"}
    assert "LEADING_INDUSTRY" not in aaa["discovery_reasons"]


def test_contract_is_backward_compatible_and_additive(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 110))
    _write_history(tmp_path, "AAA", _series(100, 140))
    original = _bucket("AAA")
    result = enrich_swing_discovery_bucket(
        original,
        _report({"underlying_symbol": "AAA", "source_confluence": {"level": "STRONG"}}),
        [{"underlying_symbol": "AAA"}],
        history_dir=tmp_path,
    )
    assert result["schema_version"] == "1.0"
    assert result["strategy_id"] == "SWING-001"
    candidate = result["candidates"][0]
    for field in ("underlying_symbol", "discovery_status", "evidence_sources"):
        assert field in candidate
    assert "relative_leadership" in candidate
    assert "entry_score" not in candidate
    assert "opportunity_quality" not in candidate


def test_ranking_is_deterministic_and_score_first(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 110))
    _write_history(tmp_path, "AAA", _series(100, 115))
    _write_history(tmp_path, "BBB", _series(100, 150))
    weekly = _report(
        {"underlying_symbol": "AAA", "source_confluence": {"level": "NONE"}},
        {"underlying_symbol": "BBB", "source_confluence": {"level": "NONE"}},
    )
    observations = [{"underlying_symbol": "AAA"}, {"underlying_symbol": "BBB"}]
    result = enrich_swing_discovery_bucket(_bucket("AAA", "BBB"), weekly, observations, history_dir=tmp_path)
    assert [row["underlying_symbol"] for row in result["candidates"]] == ["BBB", "AAA"]


def test_theme_momentum_is_only_used_when_explicit(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 110))
    _write_history(tmp_path, "AAA", _series(100, 140))
    result = enrich_swing_discovery_bucket(
        _bucket("AAA"),
        _report({"underlying_symbol": "AAA", "themes": ["AI"], "source_confluence": {"level": "NONE"}}),
        [{"underlying_symbol": "AAA", "themes": ["AI"], "theme_momentum": {"classification": "RISING"}}],
        history_dir=tmp_path,
    )
    candidate = result["candidates"][0]
    assert candidate["theme_leadership"]["classification"] == "RISING"
    assert "RISING_THEME" in candidate["discovery_reasons"]


def test_trapper_2x_rule_requires_positive_stock_and_meaningful_positive_benchmark():
    assert has_trapper_2x_spy_evidence(20.0, 5.0, 15.0, 4.0) is True
    assert has_trapper_2x_spy_evidence(-20.0, 5.0, 15.0, 4.0) is False
    assert has_trapper_2x_spy_evidence(20.0, 0.5, 19.5, 40.0) is False
    assert has_trapper_2x_spy_evidence(20.0, -5.0, 25.0, -4.0) is False


def test_trapper_reason_uses_same_horizon_flag_as_classifier(tmp_path):
    _write_history(tmp_path, "SPY", _series(100, 110))
    _write_history(tmp_path, "AAA", _series(100, 150))
    result = enrich_swing_discovery_bucket(
        _bucket("AAA"),
        _report({"underlying_symbol": "AAA", "source_confluence": {"level": "NONE"}}),
        [{"underlying_symbol": "AAA"}],
        history_dir=tmp_path,
    )
    candidate = result["candidates"][0]
    flags = [
        row["trapper_2x_spy_evidence"]
        for row in candidate["relative_leadership"]["horizons"].values()
        if row.get("evidence_status") == "AVAILABLE"
    ]
    assert ("TRAPPER_2X_SPY_EVIDENCE" in candidate["discovery_reasons"]) is any(flags)
