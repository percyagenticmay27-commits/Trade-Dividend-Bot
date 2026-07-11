import json
from pathlib import Path

import candidate_discovery_engine as engine


def test_public_functions_exist():
    assert callable(engine.discover_candidates)
    assert callable(engine.build_candidate_discovery_report)
    assert callable(engine.write_candidate_discovery)


def test_discovers_symbols_from_multiple_sources_without_duplicates():
    payloads = {
        "MARKET_SNAPSHOT": {"records": [{"symbol": "QQQI"}, {"symbol": "SGOV"}]},
        "WATCHLIST": {"watchlist": ["qqqi", "TQQQ"]},
        "PORTFOLIO": {"holdings": [{"symbol": "SGOV"}]},
    }
    report = engine.build_candidate_discovery_report(payloads)
    assert report["symbols"] == ["QQQI", "SGOV", "TQQQ"]
    assert report["candidate_count"] == 3


def test_current_holding_and_watchlist_flags_are_preserved():
    report = engine.build_candidate_discovery_report({
        "PORTFOLIO": {"holdings": [{"symbol": "SCHD"}]},
        "WATCHLIST": {"symbols": ["SCHD", "AMDW"]},
    })
    by_symbol = {item["symbol"]: item for item in report["candidates"]}
    assert by_symbol["SCHD"]["currently_held"] is True
    assert by_symbol["SCHD"]["on_watchlist"] is True
    assert by_symbol["AMDW"]["currently_held"] is False


def test_market_snapshot_controls_scoring_readiness():
    report = engine.build_candidate_discovery_report({
        "MARKET_SNAPSHOT": {"records": [
            {"symbol": "QQQI", "is_stale": False},
            {"symbol": "TQQQ", "is_stale": True},
        ]},
        "WATCHLIST": {"symbols": ["QQQI", "TQQQ", "SPYI"]},
    })
    by_symbol = {item["symbol"]: item for item in report["candidates"]}
    assert by_symbol["QQQI"]["status"] == "READY_FOR_SCORING"
    assert by_symbol["TQQQ"]["status"] == "READY_FOR_REFRESH"
    assert by_symbol["SPYI"]["status"] == "READY_FOR_REFRESH"


def test_nested_pair_symbols_are_discovered():
    report = engine.build_candidate_discovery_report({
        "OPPORTUNITY_PAIRING": {
            "pairs": [{"income_symbol": "QQQI", "growth_symbol": "TQQQ"}]
        }
    })
    assert report["symbols"] == ["QQQI", "TQQQ"]


def test_explicit_symbols_are_normalized_and_deduplicated():
    report = engine.build_candidate_discovery_report({}, explicit_symbols=[" amdW ", "AMDW", "GOOW"])
    assert report["symbols"] == ["AMDW", "GOOW"]
    assert all("EXPLICIT" in item["sources"] for item in report["candidates"])


def test_invalid_symbols_are_ignored():
    report = engine.build_candidate_discovery_report(
        {"WATCHLIST": {"symbols": ["", "N/A", "BAD SYMBOL", None, "AMD"]}}
    )
    assert report["symbols"] == ["AMD"]


def test_no_candidates_returns_warning_not_error():
    report = engine.build_candidate_discovery_report({})
    assert report["candidate_count"] == 0
    assert report["warnings"]
    assert report["errors"] == []


def test_source_files_are_recorded():
    report = engine.build_candidate_discovery_report(
        {"WATCHLIST": {"symbols": ["AVGW"]}},
        {"WATCHLIST": "custom_watchlist.json"},
    )
    assert report["candidates"][0]["source_files"] == ["custom_watchlist.json"]


def test_write_outputs_json_csv_and_markdown(tmp_path: Path):
    (tmp_path / "market_data_snapshot.json").write_text(
        json.dumps({"records": [{"symbol": "SGOV", "is_stale": False}]}),
        encoding="utf-8",
    )
    (tmp_path / "watchlist_report.json").write_text(
        json.dumps({"symbols": ["QQQI"]}), encoding="utf-8"
    )
    report = engine.write_candidate_discovery(root_path=str(tmp_path))
    assert report["candidate_count"] == 2
    assert (tmp_path / "candidate_discovery.json").exists()
    assert (tmp_path / "candidate_discovery.csv").exists()
    assert (tmp_path / "candidate_discovery.md").exists()


def test_malformed_optional_file_creates_warning(tmp_path: Path):
    (tmp_path / "watchlist_report.json").write_text("{bad", encoding="utf-8")
    report = engine.write_candidate_discovery(root_path=str(tmp_path), explicit_symbols=["SCHD"])
    assert report["candidate_count"] == 1
    assert any("watchlist_report.json" in warning for warning in report["warnings"])


def test_report_is_unbiased_and_paper_only():
    report = engine.build_candidate_discovery_report({}, explicit_symbols=["AMDW", "SPYI", "SGOV"])
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True
    assert report["optimization_profile"] == "MAXIMUM_TOTAL_WEALTH"
    assert report["symbols"] == ["AMDW", "SGOV", "SPYI"]


def test_candidate_type_is_single_instrument_for_discovery_stage():
    report = engine.build_candidate_discovery_report({}, explicit_symbols=["QQQI"])
    assert report["candidates"][0]["candidate_type"] == "SINGLE_INSTRUMENT"


def test_source_contains_no_restricted_execution_calls():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    forbidden = ["os.system(", "subprocess.", "place_order(", "execute_trade(", "robin_stocks"]
    for token in forbidden:
        assert token not in source
