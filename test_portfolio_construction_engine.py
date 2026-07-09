"""Tests for portfolio_construction_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import portfolio_construction_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine,"ConstructedHolding")
    assert hasattr(engine,"PortfolioConstructionReport")


def test_public_functions_exist():
    for name in ["construct_portfolio","build_portfolio_construction_report","validate_portfolio_construction_report","write_portfolio_construction_report_json","read_portfolio_construction_report_json","write_portfolio_construction_report_csv","format_portfolio_construction_report_markdown","write_portfolio_construction_report_markdown"]:
        assert callable(getattr(engine,name))


def test_default_report_valid_cash_shield_only():
    p=engine.build_portfolio_construction_report()
    assert engine.validate_portfolio_construction_report(p) is True
    assert p["paper_trade_mode"] is True
    assert p["live_trading_enabled"] is False
    assert p["broker_execution_enabled"] is False
    assert p["reporting_only"] is True
    assert p["constructed_holdings"][0]["symbol"]=="SGOV"
    assert p["constructed_holdings"][0]["construction_status"]=="CASH_SHIELD"


def test_constructs_best_two_plus_cash_shield():
    allocations=[
        {"symbol":"AAA","allocation_action":"ALLOCATE","target_allocation_dollars":200,"allocation_score":100},
        {"symbol":"BBB","allocation_action":"ALLOCATE","target_allocation_dollars":150,"allocation_score":90},
        {"symbol":"CCC","allocation_action":"ALLOCATE","target_allocation_dollars":100,"allocation_score":80},
    ]
    p=engine.build_portfolio_construction_report(allocations,portfolio_value=500,target_holding_count=2)
    symbols=[x["symbol"] for x in p["constructed_holdings"]]
    assert symbols[:2]==["AAA","BBB"]
    assert "SGOV" in symbols
    assert p["deferred_count"]==1


def test_below_minimum_position_rejected():
    p=engine.build_portfolio_construction_report([{"symbol":"AAA","allocation_action":"ALLOCATE","target_allocation_dollars":10,"allocation_score":100}],portfolio_value=500)
    assert p["rejected_count"]==1
    assert p["risk_status"]=="ERROR"


def test_non_allocate_deferred():
    p=engine.build_portfolio_construction_report([{"symbol":"AAA","allocation_action":"SKIP_SMALL_POSITION","target_allocation_dollars":100,"allocation_score":100}],portfolio_value=500)
    assert p["deferred_count"]==1


def test_max_position_cap_enforced():
    p=engine.build_portfolio_construction_report([{"symbol":"AAA","allocation_action":"ALLOCATE","target_allocation_dollars":400,"allocation_score":100}],portfolio_value=500,max_position_pct=0.40)
    row=p["constructed_holdings"][0]
    assert row["target_allocation_dollars"]==200.0
    assert row["risk_status"]=="WARNING"


def test_validate_rejects_malformed_payload():
    for x in [None,[],"bad"]:
        with pytest.raises(ValueError): engine.validate_portfolio_construction_report(x)


def test_validate_rejects_missing_required_fields():
    p=engine.build_portfolio_construction_report()
    for f in engine.REPORT_REQUIRED_FIELDS:
        bad=dict(p); bad.pop(f,None)
        with pytest.raises(ValueError): engine.validate_portfolio_construction_report(bad)


def test_validate_rejects_wrong_safety_flags():
    p=engine.build_portfolio_construction_report()
    for f,v in [("paper_trade_mode",False),("live_trading_enabled",True),("broker_execution_enabled",True),("reporting_only",False)]:
        bad=dict(p); bad[f]=v
        with pytest.raises(ValueError): engine.validate_portfolio_construction_report(bad)


def test_json_csv_markdown_outputs(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    p=engine.write_portfolio_construction_report_json()
    assert engine.read_portfolio_construction_report_json()==p
    engine.write_portfolio_construction_report_csv()
    engine.write_portfolio_construction_report_markdown()
    assert Path("portfolio_construction_report.json").exists()
    assert Path("portfolio_construction_report.csv").exists()
    assert Path("portfolio_construction_report.md").exists()
    md=engine.format_portfolio_construction_report_markdown(p)
    assert "# Portfolio Construction Report" in md
    assert "## Constructed Holdings" in md
    assert "## Safety Guarantees" in md


def test_static_safety_no_robinhood_or_order_execution():
    src=Path(engine.__file__).read_text(encoding="utf-8").lower()
    for item in ["import robinhood","from robinhood","import robin_stocks","from robin_stocks","place_order(","submit_order(","execute_order(","real_order","live_order"]:
        assert item not in src


def test_static_safety_no_subprocess_os_system_or_internet():
    src=Path(engine.__file__).read_text(encoding="utf-8")
    for item in ["import subprocess","from subprocess","subprocess.","Popen(","os.system(",".system(","requests.","urllib.request","http.client","socket."]:
        assert item not in src
