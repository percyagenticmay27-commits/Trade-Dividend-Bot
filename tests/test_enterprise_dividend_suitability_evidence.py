from __future__ import annotations

import json
from pathlib import Path

from enterprise_dividend_suitability_evidence import (
    build_vehicle_evidence,
    collect_suitability_evidence,
)


def _history():
    return {
        "provider": "TEST",
        "rows": [
            {"date": f"2026-07-{day:02d}", "adj_close": 100 + day, "volume": 100_000}
            for day in range(1, 21)
        ],
    }


def test_live_history_builds_return_and_liquidity_without_inference():
    row = build_vehicle_evidence(
        "AMDY", "INCOME_ETF",
        {
            "reviewed_at": "2026-07-20",
            "fund_inception_date": "2023-09-18",
            "expense_ratio_percent": 1.0,
            "latest_distribution_roc_percent": 91.79,
            "sources": [{"source_url": "https://example.test/amdy"}],
        },
        _history(), {},
    )
    assert row["total_return_1y_percent"] == 18.811881
    assert row["latest_dollar_volume"] == 11050000.0
    assert row["expense_ratio_percent"] == 1.0
    assert row["latest_distribution_roc_percent"] == 91.79


def test_direct_equity_normalizes_provider_dividend_yield():
    row = build_vehicle_evidence(
        "DUK", "DIRECT_DIVIDEND_EQUITY",
        {
            "reviewed_at": "2026-07-20",
            "dividend_cut_last_12m": False,
            "sources": [{"source_url": "https://example.test/duk"}],
        },
        _history(), {"dividend_yield": 0.035},
    )
    assert row["forward_dividend_yield_percent"] == 3.5
    assert row["dividend_cut_last_12m"] is False


class _Service:
    def get_history(self, symbol, period, interval):
        return _history()

    def get_quote(self, symbol):
        return {"dividend_yield": 0.03}


def test_collector_refreshes_only_reviewed_profiled_mappings():
    report = collect_suitability_evidence(
        {"candidates": [
            {"income_symbol": "DUK", "mapping_type": "DIRECT_DIVIDEND_EQUITY"},
            {"income_symbol": "UNKNOWN", "mapping_type": "DIRECT_DIVIDEND_EQUITY"},
        ]},
        {"profiles": [{
            "income_symbol": "DUK", "reviewed": True, "reviewed_at": "2026-07-20",
            "dividend_cut_last_12m": False,
            "sources": [{"source_url": "https://example.test/duk"}],
        }]},
        _Service(),
    )
    assert [row["income_symbol"] for row in report["vehicles"]] == ["DUK"]
    assert len(report["warnings"]) == 1
    assert report["read_only_market_data"] is True
    assert report["inference_allowed"] is False


def test_production_profiles_cover_current_mapping_catalog():
    mappings = json.loads(Path("configs/dividend_discovery_income_mappings.json").read_text())
    profiles = json.loads(Path("configs/dividend_suitability_profiles.json").read_text())
    mapped = {row["income_symbol"] for row in mappings["mappings"]}
    profiled = {row["income_symbol"] for row in profiles["profiles"]}
    assert mapped == profiled
    assert all(row["reviewed"] is True for row in profiles["profiles"])
    assert all(row["sources"] for row in profiles["profiles"])
