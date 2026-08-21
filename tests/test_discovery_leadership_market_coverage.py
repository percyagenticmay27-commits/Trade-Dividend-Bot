from __future__ import annotations

import json

import scripts.generate_enterprise_weekly_market_discovery as generator


def _report(*symbols):
    return {
        "candidates": [
            {"underlying_symbol": symbol, "nomination_eligible": True}
            for symbol in symbols
        ]
    }


def test_required_coverage_always_includes_spy_and_nominees():
    assert generator._required_leadership_symbols(_report("NVDA", "AVGO")) == [
        "AVGO",
        "NVDA",
        "SPY",
    ]


def test_ineligible_nominee_does_not_expand_market_coverage():
    report = {
        "candidates": [
            {"underlying_symbol": "NVDA", "nomination_eligible": True},
            {"underlying_symbol": "ZZZZ", "nomination_eligible": False},
        ]
    }
    assert generator._required_leadership_symbols(report) == ["NVDA", "SPY"]


def test_existing_snapshot_coverage_does_not_refresh(tmp_path, monkeypatch):
    snapshot = {
        "records": [
            {"symbol": "SPY"},
            {"symbol": "NVDA"},
        ]
    }
    (tmp_path / "market_data_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")

    def unexpected_refresh(**kwargs):
        raise AssertionError("market snapshot should not refresh when coverage is complete")

    monkeypatch.setattr(generator, "write_market_data_snapshot", unexpected_refresh)
    result = generator._ensure_market_snapshot_coverage(tmp_path, _report("NVDA"))
    assert generator._snapshot_symbols(result) == {"SPY", "NVDA"}


def test_missing_spy_refreshes_through_ai_cio_market_data_layer(tmp_path, monkeypatch):
    existing = {"records": [{"symbol": "NVDA"}]}
    (tmp_path / "market_data_snapshot.json").write_text(json.dumps(existing), encoding="utf-8")
    calls = []

    def fake_refresh(*, root_path, symbols, force_refresh):
        calls.append(
            {
                "root_path": root_path,
                "symbols": list(symbols),
                "force_refresh": force_refresh,
            }
        )
        return {"records": [{"symbol": "NVDA"}, {"symbol": "SPY"}]}

    monkeypatch.setattr(generator, "write_market_data_snapshot", fake_refresh)
    result = generator._ensure_market_snapshot_coverage(tmp_path, _report("NVDA"))

    assert calls == [
        {
            "root_path": str(tmp_path),
            "symbols": ["NVDA", "SPY"],
            "force_refresh": False,
        }
    ]
    assert generator._snapshot_symbols(result) == {"NVDA", "SPY"}
