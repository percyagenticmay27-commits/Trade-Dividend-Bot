from __future__ import annotations

import entry_score_engine as entry_engine
from dividend_entry_gate import evaluate_entry_gate
from stage_input_adapters import build_portfolio_decision_candidates


def _record(symbol: str, closes: list[float], *, stale: bool = False) -> dict:
    rows = []
    for i, close in enumerate(closes):
        rows.append({
            "date": f"2026-01-{(i % 28) + 1:02d}",
            "open": close - 0.5,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "volume": 100000 + i * 100,
        })
    return {
        "symbol": symbol,
        "is_stale": stale,
        "history": {"rows": rows, "data_source": "TEST"},
    }


def _snapshot(*records: dict) -> dict:
    return {"records": list(records)}


def test_default_no_snapshot_preserves_unknown_fail_closed_contract() -> None:
    report = entry_engine.build_entry_score_report()
    assert report["entry_score"] == 0
    assert report["entry_status"] == "UNKNOWN"
    assert report["entries"] == []
    assert report["symbol_specific"] is False


def test_symbol_specific_entry_uses_real_history_and_publishes_reasons() -> None:
    closes = [100 + i * 0.25 for i in range(89)] + [122.0, 121.6, 123.5]
    report = entry_engine.build_entry_score_report(_snapshot(_record("AAA", closes)))
    assert report["symbol_specific"] is True
    assert report["entry_count"] == 1
    row = report["entries"][0]
    assert row["symbol"] == "AAA"
    assert row["history_row_count"] >= 60
    assert row["technical_evidence"]["rsi14"] > 55
    assert row["technical_evidence"]["ema20"] > row["technical_evidence"]["ema50"]
    assert row["technical_evidence"]["hma50"] > 0
    assert "fast_stochastic_k" in row["technical_evidence"]
    assert row["entry_status"] in {"GOOD_ENTRY", "STRONG_ENTRY", "WATCH", "WAIT", "AVOID"}
    assert row["reasons"]


def test_below_50_rsi_is_explicit_wait_blocker() -> None:
    closes = [150 - i * 0.35 for i in range(90)]
    report = entry_engine.build_entry_score_report(_snapshot(_record("BAD", closes)))
    row = report["entries"][0]
    assert row["technical_evidence"]["rsi14"] < 50
    assert "RSI14_BELOW_50" in row["reasons"]
    assert row["entry_status"] not in {"GOOD_ENTRY", "STRONG_ENTRY"}
    assert "RSI14 must recover above 55" in row["requirements_for_buy"]


def test_insufficient_history_remains_unknown_instead_of_fabricated() -> None:
    report = entry_engine.build_entry_score_report(_snapshot(_record("SHORT", [100 + i for i in range(20)])))
    row = report["entries"][0]
    assert row["entry_score"] == 0
    assert row["entry_status"] == "UNKNOWN"
    assert any(reason.startswith("INSUFFICIENT_") for reason in row["reasons"])


def test_stale_market_data_cannot_be_good_entry() -> None:
    closes = [100 + i * 0.2 for i in range(90)]
    report = entry_engine.build_entry_score_report(_snapshot(_record("STALE", closes, stale=True)))
    row = report["entries"][0]
    assert "STALE_MARKET_DATA" in row["reasons"]
    assert row["entry_status"] not in {"GOOD_ENTRY", "STRONG_ENTRY"}


def test_gate_selects_symbol_specific_entry_instead_of_global_aggregate() -> None:
    report = {
        "entry_score": 90,
        "entry_status": "STRONG_ENTRY",
        "symbol_specific": True,
        "entries": [{
            "symbol": "NUGT",
            "entry_score": 61,
            "entry_status": "WATCH",
            "reasons": ["RSI14_NOT_ABOVE_55"],
            "requirements_for_buy": ["RSI14 must rise above 55"],
        }],
    }
    watchlist = {"watchlist": [{"symbol": "NUGT", "status": "READY", "market_data_stale": False, "currently_held": False, "opportunity_score": 82}]}
    decision = evaluate_entry_gate(
        symbol="NUGT", pair="NUGT", sleeve="A", signal_symbol="NUGT",
        technical_snapshot={"signal": "BUY"}, watchlist_report=watchlist,
        entry_score_report=report, currently_held=False,
    )
    assert decision["approved"] is False
    assert decision["entry_status"] == "WATCH"
    assert "ENTRY_STATUS_NOT_APPROVED_WATCH" in decision["reasons"]
    assert "ENTRY_EVIDENCE_RSI14_NOT_ABOVE_55" in decision["reasons"]
    assert decision["entry_requirements"] == ["RSI14 must rise above 55"]


def test_portfolio_adapter_propagates_symbol_specific_entry_score() -> None:
    payloads = {
        "opportunity_pairing": {"opportunities": [{"symbol": "AAA", "combined_score": 80}, {"symbol": "BBB", "combined_score": 70}]},
        "entry_score": {"entry_score": 10, "entry_status": "AVOID", "entries": [
            {"symbol": "AAA", "entry_score": 88, "entry_status": "STRONG_ENTRY", "reasons": []},
            {"symbol": "BBB", "entry_score": 52, "entry_status": "WAIT", "reasons": ["RSI14_BELOW_50"]},
        ]},
        "dividend_ranking": {"rankings": []},
        "conviction": {},
        "momentum_score": {},
    }
    rows = build_portfolio_decision_candidates(payloads)
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["AAA"]["entry_score"] == 88
    assert by_symbol["AAA"]["entry_status"] == "STRONG_ENTRY"
    assert by_symbol["BBB"]["entry_score"] == 52
    assert by_symbol["BBB"]["entry_status"] == "WAIT"
    assert by_symbol["BBB"]["entry_reasons"] == ["RSI14_BELOW_50"]
