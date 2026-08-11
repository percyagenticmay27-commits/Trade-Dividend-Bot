from __future__ import annotations

import csv
import json
from pathlib import Path

from src.dividend_bot.dividend_dashboard_evidence import build_dividend_dashboard_evidence


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_current_holding_owner_reaches_dashboard_evidence(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {
        "pairs": {
            "AAA / BBB": {
                "a_shares": 2.0,
                "b_shares": 0.0,
                "last_prices": {"A": 10.0, "B": 20.0},
                "sgov_balance": 0.0,
                "total_dividends_received": 0.0,
                "a_strategy_owner": "STRATEGY_A",
                "strategy_owner": "STRATEGY_A",
                "strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
            }
        }
    })
    payload = build_dividend_dashboard_evidence(tmp_path)
    holding = next(row for row in payload["holdings"] if row["symbol"] == "AAA")
    assert holding["strategy_owner"] == "STRATEGY_A"
    assert holding["entry_method"] == "STRATEGY_A"
    assert holding["strategy_ownership_source"] == "QUALIFIED_ENTRY_GATE"
    assert holding["exit_state"] == "UNKNOWN"
    assert holding["sell_trigger"] is False


def test_strategy_a_buffered_warning_reaches_dashboard_without_becoming_sell(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {
        "pairs": {
            "AAA / BBB": {
                "a_shares": 2.0,
                "b_shares": 0.0,
                "last_prices": {"A": 10.0, "B": 20.0},
                "sgov_balance": 0.0,
                "total_dividends_received": 0.0,
                "a_strategy_owner": "STRATEGY_A",
                "strategy_owner": "STRATEGY_A",
                "strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
            }
        }
    })
    _write_json(tmp_path / "entry_score_report.json", {
        "entries": [{
            "symbol": "AAA",
            "strategy_signals": {
                "strategy_a": {
                    "sell_trigger": False,
                    "sell_reasons": [],
                    "exit_warning_active": True,
                    "exit_buffered": True,
                    "exit_warning_reasons": ["STOCH_RSI_D_CROSSED_ABOVE_K"],
                },
                "strategy_b": {"sell_trigger": False, "sell_reason": None},
            },
        }]
    })

    payload = build_dividend_dashboard_evidence(tmp_path)
    holding = next(row for row in payload["holdings"] if row["symbol"] == "AAA")
    assert holding["strategy_owner"] == "STRATEGY_A"
    assert holding["position_status"] == "OPEN"
    assert holding["exit_state"] == "WARNING_BUFFERED"
    assert holding["exit_warning_active"] is True
    assert holding["exit_buffered"] is True
    assert holding["exit_warning_reasons"] == ["STOCH_RSI_D_CROSSED_ABOVE_K"]
    assert holding["sell_trigger"] is False
    assert holding["sell_reasons"] == []
    assert holding["exit_authority_reason"] == "STRATEGY_A_EXIT_AUTHORITY"
    assert holding["exit_evidence_source"] == "entry_score_report.json"
    assert "entry_score_report.json" in payload["evidence_sources"]
    alert = next(item for item in payload["alerts"] if item["symbol"] == "AAA")
    assert alert["alert_type"] == "EXIT_WARNING_BUFFERED"
    assert alert["status"] == "MONITOR"
    assert alert["reasons"] == ["STOCH_RSI_D_CROSSED_ABOVE_K"]


def test_strategy_a_confirmed_sell_reaches_dashboard_as_confirmed_not_closed(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {
        "pairs": {
            "AAA / BBB": {
                "a_shares": 2.0,
                "b_shares": 0.0,
                "last_prices": {"A": 10.0, "B": 20.0},
                "sgov_balance": 0.0,
                "total_dividends_received": 0.0,
                "a_strategy_owner": "STRATEGY_A",
                "strategy_owner": "STRATEGY_A",
                "strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
            }
        }
    })
    _write_json(tmp_path / "entry_score_report.json", {
        "entries": [{
            "symbol": "AAA",
            "strategy_signals": {
                "strategy_a": {
                    "sell_trigger": True,
                    "sell_reasons": ["STOCH_OSC_D_CROSSED_ABOVE_K_BELOW_80"],
                    "exit_warning_active": True,
                    "exit_buffered": False,
                    "exit_warning_reasons": ["STOCH_RSI_D_CROSSED_ABOVE_K"],
                },
                "strategy_b": {"sell_trigger": False, "sell_reason": None},
            },
        }]
    })

    payload = build_dividend_dashboard_evidence(tmp_path)
    holding = next(row for row in payload["holdings"] if row["symbol"] == "AAA")
    assert holding["position_status"] == "OPEN"
    assert holding["exit_state"] == "SELL_CONFIRMED"
    assert holding["sell_trigger"] is True
    assert holding["sell_reasons"] == ["STOCH_OSC_D_CROSSED_ABOVE_K_BELOW_80"]
    alert = next(item for item in payload["alerts"] if item["symbol"] == "AAA")
    assert alert["alert_type"] == "SELL_CONFIRMED"
    assert alert["status"] == "ACTION_REQUIRED"


def test_strategy_b_does_not_inherit_strategy_a_buffer_warning(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {
        "pairs": {
            "AAA / BBB": {
                "a_shares": 2.0,
                "b_shares": 0.0,
                "last_prices": {"A": 10.0, "B": 20.0},
                "sgov_balance": 0.0,
                "total_dividends_received": 0.0,
                "a_strategy_owner": "STRATEGY_B",
                "strategy_owner": "STRATEGY_B",
                "strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
            }
        }
    })
    _write_json(tmp_path / "entry_score_report.json", {
        "entries": [{
            "symbol": "AAA",
            "strategy_signals": {
                "strategy_a": {
                    "sell_trigger": False,
                    "exit_warning_active": True,
                    "exit_buffered": True,
                    "exit_warning_reasons": ["STOCH_RSI_D_CROSSED_ABOVE_K"],
                },
                "strategy_b": {"sell_trigger": False, "sell_reason": None},
            },
        }]
    })

    payload = build_dividend_dashboard_evidence(tmp_path)
    holding = next(row for row in payload["holdings"] if row["symbol"] == "AAA")
    assert holding["strategy_owner"] == "STRATEGY_B"
    assert holding["exit_state"] == "HOLD"
    assert holding["exit_warning_active"] is False
    assert holding["exit_buffered"] is False
    assert holding["exit_warning_reasons"] == []
    assert holding["sell_trigger"] is False


def test_completed_owner_controlled_exit_reaches_lifecycle_evidence(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {
        "pairs": {
            "CCC / DDD": {
                "a_shares": 0.0,
                "b_shares": 0.0,
                "last_prices": {"A": 9.0, "B": 20.0},
                "sgov_balance": 100.0,
                "total_dividends_received": 0.0,
                "strategy_owner": None,
                "strategy_ownership_source": "CLOSED_TO_SGOV",
                "last_exit_strategy_owner": "STRATEGY_B",
                "last_exit_strategy_reasons": ["PRICE_BELOW_EMA20"],
            }
        }
    })
    with (tmp_path / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "Date", "Pair", "Sleeve", "Action", "Ticker", "Shares", "Price", "Paper_Value", "Reason"
        ])
        writer.writeheader()
        writer.writerow({
            "Date": "2026-08-01", "Pair": "CCC / DDD", "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN", "Ticker": "CCC", "Shares": "10",
            "Price": "10", "Paper_Value": "100", "Reason": "Qualified entry",
        })
        writer.writerow({
            "Date": "2026-08-05", "Pair": "CCC / DDD", "Sleeve": "A",
            "Action": "PAPER_SELL_TO_SGOV", "Ticker": "CCC", "Shares": "10",
            "Price": "9", "Paper_Value": "90", "Reason": "Strategy-owner exit: PRICE_BELOW_EMA20",
        })

    payload = build_dividend_dashboard_evidence(tmp_path)
    life = next(row for row in payload["performance_detail"]["position_lifecycle"] if row["symbol"] == "CCC")
    assert life["lifecycle_status"] == "PARKED_IN_SGOV"
    assert life["entry_method"] == "STRATEGY_B"
    assert life["exit_method"] == "STRATEGY_B"
    assert life["last_exit_strategy_owner"] == "STRATEGY_B"
    assert life["last_exit_strategy_reasons"] == ["PRICE_BELOW_EMA20"]
    assert life["last_exit_reason"] == "PRICE_BELOW_EMA20"
    assert life["strategy_exit_evidence_source"] == "paper_state.json"

def test_legacy_unassigned_holding_uses_current_underlying_consensus_without_closing(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 4.0,
                "b_shares": 3.0,
                "last_prices": {"A": 10.0, "B": 20.0},
                "sgov_balance": 0.0,
                "total_dividends_received": 0.0,
                "strategy_owner": "LEGACY_UNASSIGNED",
                "strategy_ownership_source": "LEGACY_PRE_OWNERSHIP_POSITION",
                "last_signal": {"A": "BUY", "B": "BUY"},
            }
        }
    })
    _write_json(tmp_path / "entry_score_report.json", {
        "generated_at_utc": "2026-08-10T21:00:00Z",
        "entries": [{
            "symbol": "AMD",
            "strategy_signals": {
                "strategy_a": {
                    "sell_trigger": True,
                    "sell_reasons": ["STOCH_OSC_D_CROSSED_ABOVE_K"],
                    "exit_warning_active": False,
                    "exit_buffered": False,
                    "exit_warning_reasons": [],
                },
                "strategy_b": {
                    "sell_trigger": True,
                    "sell_reason": "PRICE_BELOW_EMA20",
                },
            },
        }],
    })

    payload = build_dividend_dashboard_evidence(tmp_path)
    holdings = [
        row for row in payload["holdings"]
        if row["symbol"] in {"AMDW", "AMDL"}
    ]

    assert len(holdings) == 2
    assert all(row["strategy_owner"] == "LEGACY_UNASSIGNED" for row in holdings)
    assert all(row["strategy_ownership_source"] == "LEGACY_PRE_OWNERSHIP_POSITION" for row in holdings)
    assert all(row["position_status"] == "OPEN" for row in holdings)
    assert all(row["exit_state"] == "SELL_CONFIRMED" for row in holdings)
    assert all(row["sell_trigger"] is True for row in holdings)
    assert all(row["exit_signal_symbol"] == "AMD" for row in holdings)
    assert all(row["exit_evidence_source"] == "entry_score_report.json" for row in holdings)
    assert all(row["exit_evidence_generated_at_utc"] == "2026-08-10T21:00:00Z" for row in holdings)



def test_legacy_warning_explains_missing_consensus_once_per_pair(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 4.0,
                "b_shares": 3.0,
                "last_prices": {"A": 10.0, "B": 20.0},
                "sgov_balance": 0.0,
                "total_dividends_received": 0.0,
                "strategy_owner": "LEGACY_UNASSIGNED",
                "strategy_ownership_source": "LEGACY_PRE_OWNERSHIP_POSITION",
            }
        }
    })
    _write_json(tmp_path / "entry_score_report.json", {
        "entries": [{
            "symbol": "AMD",
            "strategy_signals": {
                "strategy_a": {
                    "sell_trigger": False,
                    "sell_reasons": [],
                    "exit_warning_active": False,
                    "exit_buffered": False,
                    "exit_warning_reasons": [],
                },
                "strategy_b": {
                    "sell_trigger": True,
                    "sell_reason": "PRICE_BELOW_EMA20",
                },
            },
        }],
    })

    payload = build_dividend_dashboard_evidence(tmp_path)
    alerts = [
        item for item in payload["alerts"]
        if item.get("alert_type") == "EXIT_WARNING_BUFFERED"
    ]

    assert len(alerts) == 1
    assert alerts[0]["pair"] == "AMDW / AMDL"
    assert "Strategy B currently has a sell condition" in alerts[0]["message"]
    assert "Strategy A has not confirmed a sale" in alerts[0]["message"]
    assert "requires both Strategy A and Strategy B to confirm SELL" in alerts[0]["message"]
    assert alerts[0]["reasons"] == ["PRICE_BELOW_EMA20"]
