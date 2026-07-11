from pathlib import Path

import pytest

import single_instrument_total_wealth_evaluator as evaluator


def sample_record(symbol="AAA", stale=False):
    closes = [100 + index * 0.4 for index in range(120)]
    return {
        "symbol": symbol,
        "price": closes[-1],
        "previous_close": closes[-2],
        "market_cap": 50_000_000_000,
        "dividend_yield": 0.04,
        "beta": 1.1,
        "volume": 2_000_000,
        "sector": "Technology",
        "industry": "Semiconductors",
        "dividend_record_count": 20,
        "dividend_total": 5.0,
        "history": [{"close": value} for value in closes],
        "is_stale": stale,
    }


def test_public_functions_exist():
    assert callable(evaluator.evaluate_single_instrument)
    assert callable(evaluator.build_single_instrument_total_wealth_report)
    assert callable(evaluator.write_single_instrument_total_wealth)


def test_positive_growth_and_income_are_scored():
    candidate = evaluator.evaluate_single_instrument(sample_record(), market_regime="BULL")
    assert candidate["expected_capital_appreciation"] > 50
    assert candidate["expected_income"] > 0
    assert candidate["momentum_trend_quality"] >= 50


def test_high_yield_does_not_remove_risk_penalties():
    record = sample_record()
    record["dividend_yield"] = 0.30
    record["history"] = [{"close": value} for value in [100, 80, 60, 50, 45] * 25]
    candidate = evaluator.evaluate_single_instrument(record)
    assert candidate["expected_income"] == 100
    assert candidate["drawdown_risk"] > 0
    assert candidate["distribution_sustainability"] < 100


def test_stale_data_reduces_confidence():
    fresh = evaluator.evaluate_single_instrument(sample_record(stale=False))
    stale = evaluator.evaluate_single_instrument(sample_record(stale=True))
    assert stale["evidence_confidence"] < fresh["evidence_confidence"]
    assert "fresh_market_data" in stale["missing_evidence"]


def test_missing_symbol_rejected():
    with pytest.raises(ValueError):
        evaluator.evaluate_single_instrument({"price": 10})


def test_missing_history_is_reported_as_missing_evidence():
    record = sample_record()
    record.pop("history")
    candidate = evaluator.evaluate_single_instrument(record)
    assert "history" in candidate["missing_evidence"]


def test_bear_regime_penalizes_high_beta_more_than_low_beta():
    high = sample_record("HIGH")
    low = sample_record("LOW")
    high["beta"] = 1.8
    low["beta"] = 0.5
    high_candidate = evaluator.evaluate_single_instrument(high, market_regime="BEAR")
    low_candidate = evaluator.evaluate_single_instrument(low, market_regime="BEAR")
    assert low_candidate["market_regime_support"] > high_candidate["market_regime_support"]


def test_report_ranks_multiple_instruments():
    strong = sample_record("STRONG")
    weak = sample_record("WEAK")
    weak["history"] = [{"close": 140 - index * 0.5} for index in range(120)]
    report = evaluator.build_single_instrument_total_wealth_report(
        {"records": [strong, weak]}, market_regime="BULL"
    )
    assert report["instrument_count"] == 2
    assert len(report["capital_efficiency_report"]["results"]) == 2
    assert report["top_candidate_id"] in {"STRONG", "WEAK"}


def test_invalid_records_create_warning_without_crashing():
    report = evaluator.build_single_instrument_total_wealth_report(
        {"records": [sample_record(), {"price": 5}]}
    )
    assert report["instrument_count"] == 1
    assert report["warnings"]


def test_write_outputs(tmp_path: Path):
    snapshot = {"records": [sample_record()]}
    (tmp_path / "market_data_snapshot.json").write_text(
        __import__("json").dumps(snapshot), encoding="utf-8"
    )
    report = evaluator.write_single_instrument_total_wealth(root_path=str(tmp_path))
    assert report["instrument_count"] == 1
    assert (tmp_path / "single_instrument_total_wealth.json").exists()
    assert (tmp_path / "single_instrument_total_wealth.md").exists()


def test_paper_only_flags_are_enforced():
    report = evaluator.build_single_instrument_total_wealth_report({"records": [sample_record()]})
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_source_contains_no_restricted_execution_calls():
    source = Path(evaluator.__file__).read_text(encoding="utf-8")
    forbidden = ["os.system(", "subprocess.", "place_order(", "execute_trade(", "robin_stocks"]
    for token in forbidden:
        assert token not in source
