"""Tests for market_data_integration_engine.py."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import market_data_integration_engine as engine
from yahoo_finance_provider import MarketDataProviderError

class FakeService:
    def __init__(self, fail_symbol: str | None = None, stale: bool = False):
        self.fail_symbol = fail_symbol; self.stale = stale; self.calls: list[tuple[str, str]] = []
    def _check(self, kind: str, symbol: str):
        self.calls.append((kind, symbol))
        if symbol == self.fail_symbol: raise MarketDataProviderError("provider unavailable")
    def get_quote(self, symbol: str, force_refresh: bool = False):
        self._check("quote", symbol); return {"symbol":symbol,"price":100.0,"previous_close":99.0,"market_cap":1000000,"dividend_yield":0.04,"sector":"Test","data_source":"CACHE_STALE_FALLBACK" if self.stale else "LIVE_PROVIDER","is_stale":self.stale}
    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d", force_refresh: bool = False):
        self._check("history", symbol); return {"symbol":symbol,"history":[{"date":"2026-01-01","close":100.0}],"data_source":"CACHE_STALE_FALLBACK" if self.stale else "LIVE_PROVIDER","is_stale":self.stale}
    def get_dividends(self, symbol: str, period: str = "5y", force_refresh: bool = False):
        self._check("dividends", symbol); return {"symbol":symbol,"dividends":[{"date":"2026-01-01","amount":1.25}],"data_source":"CACHE_STALE_FALLBACK" if self.stale else "LIVE_PROVIDER","is_stale":self.stale}

def test_public_functions_exist():
    for name in ["configured_strategy_market_symbols","discover_market_symbols","refresh_market_data_snapshot","validate_market_data_snapshot","write_market_data_snapshot"]:
        assert callable(getattr(engine, name))

def test_configured_strategy_market_symbols_include_underlying_signal_universe():
    symbols = set(engine.configured_strategy_market_symbols())
    for symbol in {"AMD","AVGO","NVDA","GLD","NFLX","TSLA","PLTR","GOOGL","COIN","MSTR"}:
        assert symbol in symbols
    for symbol in {"AMDW","AMDL","AVGW","AVGX","NVDW","NVDX","PLTW","PLTU"}:
        assert symbol in symbols

def test_discovery_includes_configured_signal_symbols_even_without_artifacts(tmp_path: Path):
    symbols = set(engine.discover_market_symbols(str(tmp_path), symbol_files=[]))
    assert {"AMD","AVGO","NVDA","GLD","NFLX","TSLA","PLTR"}.issubset(symbols)

def test_discover_symbols_from_nested_reports(tmp_path: Path):
    payload={"holdings":[{"symbol":"schd"},{"ticker":"VYM"}],"pair":{"income_symbol":"jepi","growth_symbol":"dgro"}}
    (tmp_path/"portfolio_lifecycle_report.json").write_text(json.dumps(payload),encoding="utf-8")
    symbols=engine.discover_market_symbols(str(tmp_path),explicit_symbols=["O","schd"])
    assert {"DGRO","JEPI","O","SCHD","VYM","AMD","AVGO","NVDA"}.issubset(set(symbols))

def test_refresh_fetches_each_dataset_once_per_symbol():
    service=FakeService(); payload=engine.refresh_market_data_snapshot(["SCHD","VYM"],service)
    assert payload["status"]=="COMPLETE"; assert payload["successful_symbol_count"]==2; assert len(service.calls)==6
    assert service.calls.count(("quote","SCHD"))==1; assert service.calls.count(("history","SCHD"))==1; assert service.calls.count(("dividends","SCHD"))==1

def test_refresh_normalizes_metrics():
    row=engine.refresh_market_data_snapshot(["SCHD"],FakeService())["records"][0]
    assert row["symbol"]=="SCHD"; assert row["price"]==100.0; assert row["dividend_record_count"]==1; assert row["dividend_total"]==1.25; assert row["sector"]=="Test"

def test_no_symbols_skips_provider_and_returns_partial():
    service=FakeService(); payload=engine.refresh_market_data_snapshot([],service)
    assert payload["status"]=="PARTIAL"; assert payload["symbol_count"]==0; assert service.calls==[]; assert payload["warnings"]

def test_partial_when_one_symbol_fails():
    payload=engine.refresh_market_data_snapshot(["SCHD","BAD"],FakeService(fail_symbol="BAD"))
    assert payload["status"]=="PARTIAL"; assert payload["successful_symbol_count"]==1; assert payload["failed_symbol_count"]==1; assert any(item.startswith("BAD:") for item in payload["errors"])

def test_stale_cache_warning_is_preserved():
    payload=engine.refresh_market_data_snapshot(["SCHD"],FakeService(stale=True))
    assert payload["status"]=="COMPLETE"; assert payload["records"][0]["is_stale"] is True; assert payload["warnings"]

def test_write_json_and_csv(tmp_path: Path):
    payload=engine.write_market_data_snapshot(str(tmp_path),symbols=["SCHD"],service=FakeService())
    json_path=tmp_path/"market_data_snapshot.json"; csv_path=tmp_path/"market_data_snapshot.csv"
    assert json_path.exists(); assert csv_path.exists(); assert json.loads(json_path.read_text(encoding="utf-8"))==payload
    rows=list(csv.DictReader(csv_path.open(encoding="utf-8"))); assert any(row["symbol"]=="SCHD" for row in rows); assert "quote" not in rows[0]

def test_validate_rejects_unsafe_flags():
    payload=engine.refresh_market_data_snapshot(["SCHD"],FakeService())
    for field,value in [("paper_trade_mode",False),("live_trading_enabled",True),("broker_execution_enabled",True),("read_only_market_data",False)]:
        bad=dict(payload); bad[field]=value
        with pytest.raises(ValueError): engine.validate_market_data_snapshot(bad)
