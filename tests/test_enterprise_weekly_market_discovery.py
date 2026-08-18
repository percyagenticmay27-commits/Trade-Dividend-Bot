import json

import pytest

from enterprise_weekly_market_discovery import (
    build_dividend_projection,
    build_swing_projection,
    build_weekly_discovery,
    write_weekly_discovery,
)


def _observation(symbol="NVDA", status="RISING"):
    return {
        "underlying_symbol": symbol,
        "discovery_status": status,
        "themes": ["AI Infrastructure"],
        "source_evidence": [
            {"source": "Reuters", "mentioned_on": "2026-08-15", "story_id": "story-1"},
            {"source": "Yahoo", "mentioned_on": "2026-08-15", "story_id": "story-1", "originating_source": "Reuters"},
            {"source": "Ticker Symbol: YOU", "mentioned_on": "2026-08-16", "story_id": "story-2"},
        ],
    }


def test_strict_swing_contract_contains_underlyings_only():
    report = build_weekly_discovery([_observation()], generated_at="2026-08-16T01:00:00Z")
    swing = build_swing_projection(report)
    assert swing["schema_version"] == "1.0"
    assert swing["strategy_id"] == "SWING-001"
    assert swing["candidates"][0]["underlying_symbol"] == "NVDA"
    assert "leveraged_symbol" not in swing["candidates"][0]


def test_new_projects_to_swing_emerging_without_losing_rich_lifecycle():
    report = build_weekly_discovery([_observation(status="NEW")], generated_at="2026-08-16T01:00:00Z")
    row = build_swing_projection(report)["candidates"][0]
    assert row["discovery_status"] == "EMERGING"
    assert row["weekly_lifecycle_status"] == "NEW"


def test_story_syndication_is_one_independent_confirmation():
    report = build_weekly_discovery([_observation()], generated_at="2026-08-16T01:00:00Z")
    assert report["candidates"][0]["independent_source_count"] == 2


def test_lifecycle_retention_and_history_are_preserved(tmp_path):
    first = build_weekly_discovery([_observation(status="EMERGING")], generated_at="2026-08-09T01:00:00Z")
    second = write_weekly_discovery(tmp_path, [_observation(status="RISING")], first["candidates"], generated_at="2026-08-16T01:00:00Z")
    row = second["candidates"][0]
    assert row["previous_status"] == "EMERGING"
    assert row["consecutive_weeks_detected"] == 2
    assert row["first_discovered_at"] == "2026-08-09T01:00:00Z"
    assert len((tmp_path / "state/enterprise_market_discovery_history.jsonl").read_text().splitlines()) == 1


def test_missing_candidate_is_retained_until_expiration_then_archived_stale():
    first = build_weekly_discovery([_observation(status="COOLING")], generated_at="2026-08-09T01:00:00Z")
    retained = build_weekly_discovery([], first["candidates"], generated_at="2026-08-15T01:00:00Z")
    assert retained["candidates"][0]["underlying_symbol"] == "NVDA"
    expired = build_weekly_discovery([], first["candidates"], generated_at="2026-08-17T01:00:01Z")
    assert expired["candidates"] == []
    assert expired["expired_candidates"][0]["discovery_status"] == "STALE"
    assert build_swing_projection(expired)["candidates"] == []


def test_dividend_projection_requires_strategy_owned_income_mapping():
    report = build_weekly_discovery([_observation()], generated_at="2026-08-16T01:00:00Z")
    row = build_dividend_projection(report)["candidates"][0]
    assert row["requires_dividend_income_mapping"] is True
    assert row["promotion_authority"] == "DIVIDEND-001"


def test_duplicate_or_leveraged_nominations_fail_closed():
    with pytest.raises(ValueError, match="duplicate"):
        build_weekly_discovery([_observation(), _observation()], generated_at="2026-08-16T01:00:00Z")
    with pytest.raises(ValueError, match="leveraged"):
        build_weekly_discovery([_observation("ABC3X")], generated_at="2026-08-16T01:00:00Z")


def test_outputs_preserve_paper_safety_and_do_not_trade(tmp_path):
    report = write_weekly_discovery(tmp_path, [_observation()], generated_at="2026-08-16T01:00:00Z")
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["order_placement_enabled"] is False
    assert report["capital_movement_enabled"] is False
    swing = json.loads((tmp_path / "results/enterprise_swing_discovery_bucket.json").read_text())
    assert swing["candidates"][0]["underlying_symbol"] == "NVDA"


def test_evidence_only_candidate_is_not_sent_to_swing():
    observation = _observation(status="NEW")
    observation["nomination_eligible"] = False
    report = build_weekly_discovery([observation], generated_at="2026-08-16T01:00:00Z")
    assert report["candidates"][0]["underlying_symbol"] == "NVDA"
    assert build_swing_projection(report)["candidates"] == []
