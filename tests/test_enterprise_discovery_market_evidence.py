from enterprise_discovery_market_evidence import attach_candidate_market_evidence, build_candidate_market_evidence


def _history(symbol, closes, volumes, stale=False):
    return {
        "symbol": symbol,
        "provider": "TEST_PROVIDER",
        "is_stale": stale,
        "rows": [
            {"date": f"2026-07-{index + 1:02d}", "close": close, "volume": volume}
            for index, (close, volume) in enumerate(zip(closes, volumes))
        ],
    }


def test_market_evidence_uses_recorded_history_and_benchmark():
    closes = [100.0] * 15 + [100, 101, 102, 103, 104, 110]
    volumes = [1000.0] * 20 + [2000.0]
    spy = [100.0] * 15 + [100, 100, 101, 101, 102, 102]
    evidence = build_candidate_market_evidence(
        "SMCI", _history("SMCI", closes, volumes), _history("SPY", spy, [1000.0] * 21),
        quote={"provider": "TEST_PROVIDER", "sector": "Technology", "industry": "Hardware", "quote_type": "EQUITY"},
    )
    assert evidence["status"] == "AVAILABLE"
    assert evidence["weekly_return_percent"] == 10.0
    assert evidence["benchmark_weekly_return_percent"] == 2.0
    assert evidence["relative_strength_vs_benchmark_percent"] == 8.0
    assert evidence["volume_expansion_ratio"] == 2.0
    assert evidence["latest_dollar_volume"] == 220000.0
    assert evidence["inference_allowed"] is False


def test_non_finite_latest_close_uses_last_complete_recorded_session():
    history = _history(
        "SMCI",
        [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, float("nan")],
        [1000.0] * 6 + [2000.0],
    )
    benchmark = _history("SPY", [100.0, 100.0, 101.0, 101.0, 102.0, 103.0], [1000.0] * 6)

    evidence = build_candidate_market_evidence("SMCI", history, benchmark)

    assert evidence["latest_session"] == "2026-07-06"
    assert evidence["latest_close"] == 105.0
    assert evidence["weekly_return_percent"] == 5.0
    assert evidence["latest_volume"] == 1000.0
    assert evidence["latest_dollar_volume"] == 105000.0


def test_missing_history_is_unavailable_without_zero_fabrication():
    evidence = build_candidate_market_evidence("SMCI", {"rows": []}, None)
    assert evidence["status"] == "UNAVAILABLE"
    assert evidence["weekly_return_percent"] is None
    assert evidence["volume_expansion_ratio"] is None
    assert evidence["latest_dollar_volume"] is None


def test_only_nomination_eligible_rows_receive_live_market_refresh():
    class Service:
        def __init__(self): self.calls = []
        def get_history(self, symbol, **kwargs):
            self.calls.append(("history", symbol))
            return _history(symbol, [100.0] * 21, [1000.0] * 21)
        def get_quote(self, symbol):
            self.calls.append(("quote", symbol))
            return {"provider": "TEST_PROVIDER", "symbol": symbol}
    service = Service()
    report = {"observations": [
        {"underlying_symbol": "SMCI", "nomination_eligible": True, "evidence_warnings": ["Market evidence is unavailable; no market conclusion was inferred."]},
        {"underlying_symbol": "OTHER", "nomination_eligible": False},
    ], "warnings": []}
    attach_candidate_market_evidence(report, service)
    assert service.calls == [("history", "SPY"), ("history", "SMCI"), ("quote", "SMCI")]
    assert report["observations"][0]["market_evidence"]["status"] == "AVAILABLE"
    assert "market_evidence" not in report["observations"][1]
    assert report["market_evidence_policy"] == "AUTHORITATIVE_HISTORY_ONLY"


def test_provider_failure_discloses_unavailable_without_removing_nomination():
    class Broken:
        def get_history(self, symbol, **kwargs): raise RuntimeError("offline")
        def get_quote(self, symbol): raise AssertionError("quote should not be reached")
    report = {"observations": [{"underlying_symbol": "SMCI", "nomination_eligible": True}], "warnings": []}
    attach_candidate_market_evidence(report, Broken())
    row = report["observations"][0]
    assert row["nomination_eligible"] is True
    assert row["market_evidence"]["status"] == "UNAVAILABLE"
    assert row["market_evidence"]["inference_allowed"] is False
