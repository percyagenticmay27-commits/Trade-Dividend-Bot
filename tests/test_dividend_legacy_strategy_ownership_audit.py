from __future__ import annotations

import src.dividend_bot.dividend_legacy_strategy_ownership_audit as audit


def _market(symbol: str = "AMD") -> dict:
    rows = [
        {"date": f"2026-04-{(i % 28) + 1:02d}", "close": 100 + i, "high": 102 + i, "low": 98 + i}
        for i in range(65)
    ]
    # Ensure the reconstruction has a deterministic entry-date terminal row.
    rows.append({"date": "2026-06-18", "close": 170, "high": 172, "low": 168})
    return {"records": [{"symbol": symbol, "history": {"rows": rows}}]}


def _state(owner=None) -> dict:
    return {
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 2.0,
                "b_shares": 1.0,
                "strategy_owner": owner,
            }
        }
    }


def _log() -> list[dict]:
    return [
        {"Date": "2026-06-18", "Pair": "AMDW / AMDL", "Sleeve": "A", "Action": "PAPER_BUY_OPEN", "Ticker": "AMDW"},
        {"Date": "2026-06-18", "Pair": "AMDW / AMDL", "Sleeve": "B", "Action": "PAPER_BUY_OPEN", "Ticker": "AMDL"},
    ]


def test_unowned_pair_is_reconstructed_from_entry_date_underlying_signal(monkeypatch) -> None:
    monkeypatch.setattr(
        audit,
        "build_strategy_signals",
        lambda frame: {
            "available": True,
            "strategy_a": {"buy_trigger": True, "sell_trigger": False},
            "strategy_b": {"buy_eligible": False, "sell_trigger": False},
        },
    )
    report = audit.build_legacy_strategy_ownership_audit(
        state=_state(), log_rows=_log(), market_snapshot=_market()
    )
    assert report["state_mutated"] is False
    assert report["audited_position_count"] == 1
    row = report["positions"][0]
    assert row["pair"] == "AMDW / AMDL"
    assert row["signal_symbol"] == "AMD"
    assert row["entry_date"] == "2026-06-18"
    assert row["reconstruction"]["strategy_owner"] == "STRATEGY_A"
    assert row["migration_recommendation"] == "ELIGIBLE_FOR_EXPLICIT_BACKFILL"


def test_ambiguous_reconstruction_does_not_assign_owner(monkeypatch) -> None:
    monkeypatch.setattr(
        audit,
        "build_strategy_signals",
        lambda frame: {
            "available": True,
            "strategy_a": {"buy_trigger": True, "sell_trigger": False},
            "strategy_b": {"buy_eligible": True, "sell_trigger": False},
        },
    )
    report = audit.build_legacy_strategy_ownership_audit(
        state=_state(), log_rows=_log(), market_snapshot=_market()
    )
    row = report["positions"][0]
    assert row["reconstruction"]["strategy_owner"] is None
    assert row["reconstruction"]["reason"] == "MULTIPLE_ACTIVE_ENTRY_STRATEGIES_REQUIRE_SELECTION_POLICY"
    assert row["migration_recommendation"] == "KEEP_LEGACY_UNASSIGNED"
    assert report["eligible_for_explicit_backfill_count"] == 0


def test_existing_owned_position_is_not_rewritten_or_audited() -> None:
    report = audit.build_legacy_strategy_ownership_audit(
        state=_state("STRATEGY_A"), log_rows=_log(), market_snapshot=_market()
    )
    assert report["positions"] == []
    assert report["audited_position_count"] == 0


def test_missing_historical_market_evidence_stays_unassigned() -> None:
    report = audit.build_legacy_strategy_ownership_audit(
        state=_state(), log_rows=_log(), market_snapshot={"records": []}
    )
    row = report["positions"][0]
    assert row["strategy_signals"]["available"] is False
    assert row["reconstruction"]["strategy_owner"] is None
    assert row["migration_recommendation"] == "KEEP_LEGACY_UNASSIGNED"
    assert report["state_mutated"] is False
