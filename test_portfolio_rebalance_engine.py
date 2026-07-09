"""Tests for portfolio_rebalance_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import portfolio_rebalance_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine,"RebalanceCandidate")
    assert hasattr(engine,"RebalanceAction")
    assert hasattr(engine,"PortfolioRebalanceReport")


def test_public_functions_exist():
    for name in ["calculate_master_score","assign_rank","detect_sale_signals","determine_cash_reserve_target","build_rebalance_actions","build_capital_movement_ledger","build_portfolio_rebalance_report","validate_portfolio_rebalance_report","write_portfolio_rebalance_report_json","read_portfolio_rebalance_report_json","write_portfolio_rebalance_report_csv","format_portfolio_rebalance_report_markdown","write_portfolio_rebalance_report_markdown"]:
        assert callable(getattr(engine,name))


def test_default_empty_report_valid():
    p=engine.build_portfolio_rebalance_report()
    assert engine.validate_portfolio_rebalance_report(p) is True
    assert p["paper_trade_mode"] is True
    assert p["live_trading_enabled"] is False
    assert p["broker_execution_enabled"] is False
    assert p["reporting_only"] is True
    assert p["rebalance_objective"]=="BALANCED_INCOME_AND_GROWTH"


def test_master_score_weights_total_100():
    assert sum(engine.MASTER_SCORE_WEIGHTS.values())==100
    candidate={"opportunity_score":100,"conviction_score":100,"momentum_score":100,"entry_score":100,"technical_score":100,"market_regime_support":100}
    assert engine.calculate_master_score(candidate)==100.0


def test_rank_table():
    assert engine.assign_rank(95)=="A"
    assert engine.assign_rank(85)=="B"
    assert engine.assign_rank(75)=="C"
    assert engine.assign_rank(65)=="D"
    assert engine.assign_rank(55)=="E"
    assert engine.assign_rank(40)=="F"


def test_cash_reserve_adapts_to_regime():
    assert engine.determine_cash_reserve_target("BULL")==0.20
    assert engine.determine_cash_reserve_target("NEUTRAL")==0.25
    assert engine.determine_cash_reserve_target("BEAR")==0.30


def test_no_sale_signal_means_hold_even_if_better_watchlist_exists():
    holdings=[{"symbol":"AAA","opportunity_score":80,"conviction_score":80,"previous_conviction_score":80,"momentum_score":80,"entry_score":80,"technical_score":80,"market_regime_support":80,"current_allocation_dollars":100}]
    watch=[{"symbol":"BBB","opportunity_score":100,"conviction_score":100,"momentum_score":100,"entry_score":100,"technical_score":100,"market_regime_support":100}]
    p=engine.build_portfolio_rebalance_report(holdings,watch)
    assert p["rebalance_actions"][0]["recommended_action"]=="HOLD"
    assert p["rebalance_actions"][0]["sale_signals"]==[]


def test_sale_signal_reallocates_to_better_watchlist_over_threshold():
    holdings=[{"symbol":"AAA","opportunity_score":40,"conviction_score":60,"previous_conviction_score":80,"momentum_score":40,"entry_score":50,"technical_score":50,"market_regime_support":50,"current_allocation_dollars":100}]
    watch=[{"symbol":"BBB","opportunity_score":100,"conviction_score":100,"momentum_score":100,"entry_score":100,"technical_score":100,"market_regime_support":100}]
    p=engine.build_portfolio_rebalance_report(holdings,watch)
    a=p["rebalance_actions"][0]
    assert a["recommended_action"]=="REALLOCATE_TO_BETTER_OPPORTUNITY"
    assert a["destination_symbol"]=="BBB"
    assert a["capital_to_stage_in_sgov"]==100
    assert p["capital_movement_ledger"]


def test_sale_signal_reentry_when_no_better_opportunity():
    holdings=[{"symbol":"AAA","opportunity_score":49,"conviction_score":75,"previous_conviction_score":75,"momentum_score":80,"entry_score":80,"technical_score":80,"market_regime_support":80,"current_allocation_dollars":100}]
    watch=[{"symbol":"BBB","opportunity_score":50,"conviction_score":50,"momentum_score":50,"entry_score":50,"technical_score":50,"market_regime_support":50}]
    p=engine.build_portfolio_rebalance_report(holdings,watch)
    a=p["rebalance_actions"][0]
    assert a["recommended_action"]=="REENTER_ORIGINAL"
    assert a["destination_symbol"]=="AAA"


def test_sale_signal_redistributes_to_existing_holding():
    holdings=[
        {"symbol":"AAA","opportunity_score":40,"conviction_score":60,"previous_conviction_score":80,"momentum_score":40,"entry_score":50,"technical_score":50,"market_regime_support":50,"current_allocation_dollars":100},
        {"symbol":"CCC","opportunity_score":95,"conviction_score":95,"previous_conviction_score":95,"momentum_score":95,"entry_score":95,"technical_score":95,"market_regime_support":95,"current_allocation_dollars":100},
    ]
    p=engine.build_portfolio_rebalance_report(holdings,[])
    first=[a for a in p["rebalance_actions"] if a["symbol"]=="AAA"][0]
    assert first["recommended_action"]=="REDISTRIBUTE_TO_PORTFOLIO"
    assert first["destination_symbol"]=="CCC"


def test_detect_sale_signals_must_haves():
    c={"opportunity_score":40,"conviction_score":70,"previous_conviction_score":90,"momentum_score":40,"strategy_exit":True}
    signals=engine.detect_sale_signals(c)
    assert "OPPORTUNITY_BELOW_THRESHOLD" in signals
    assert "CONVICTION_DECREASE" in signals
    assert "MOMENTUM_NEGATIVE" in signals
    assert "STRATEGY_EXIT" in signals


def test_validate_rejects_malformed_payload():
    for x in [None,[],"bad"]:
        with pytest.raises(ValueError): engine.validate_portfolio_rebalance_report(x)


def test_validate_rejects_missing_required_fields():
    p=engine.build_portfolio_rebalance_report()
    for f in engine.REPORT_REQUIRED_FIELDS:
        bad=dict(p); bad.pop(f,None)
        with pytest.raises(ValueError): engine.validate_portfolio_rebalance_report(bad)


def test_validate_rejects_wrong_safety_flags():
    p=engine.build_portfolio_rebalance_report()
    for f,v in [("paper_trade_mode",False),("live_trading_enabled",True),("broker_execution_enabled",True),("reporting_only",False)]:
        bad=dict(p); bad[f]=v
        with pytest.raises(ValueError): engine.validate_portfolio_rebalance_report(bad)


def test_json_csv_markdown_outputs(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    p=engine.write_portfolio_rebalance_report_json()
    assert engine.read_portfolio_rebalance_report_json()==p
    engine.write_portfolio_rebalance_report_csv()
    engine.write_portfolio_rebalance_report_markdown()
    assert Path("portfolio_rebalance_report.json").exists()
    assert Path("portfolio_rebalance_report.csv").exists()
    assert Path("portfolio_rebalance_report.md").exists()
    md=engine.format_portfolio_rebalance_report_markdown(p)
    assert "# Portfolio Rebalance Report" in md
    assert "## Investment Constitution" in md
    assert "## Safety Guarantees" in md


def test_static_safety_no_robinhood_or_order_execution():
    src=Path(engine.__file__).read_text(encoding="utf-8").lower()
    for item in ["import robinhood","from robinhood","import robin_stocks","from robin_stocks","place_order(","submit_order(","execute_order(","real_order","live_order"]:
        assert item not in src


def test_static_safety_no_subprocess_os_system_or_internet():
    src=Path(engine.__file__).read_text(encoding="utf-8")
    for item in ["import subprocess","from subprocess","subprocess.","Popen(","os.system(",".system(","requests.","urllib.request","http.client","socket."]:
        assert item not in src
