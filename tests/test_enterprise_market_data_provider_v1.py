from __future__ import annotations
import json
from datetime import datetime, timezone
import pytest
from src.dividend_bot.enterprise_market_data_provider import EnterpriseMarketDataProvider, FreshnessPolicy, MarketDataUnavailable

NOW = datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc)

class Source:
    def __init__(self, name, quote=None, history=None, error=None): self.name, self.quote, self.history, self.error = name, quote, history, error
    def get_quote(self, symbol):
        if self.error: raise self.error
        return dict(self.quote)
    def get_history(self, symbol, period, interval):
        if self.error: raise self.error
        return dict(self.history)

def quote(provider="ROBINHOOD_MCP", ts="2026-08-04T16:59:00+00:00"):
    return {"symbol":"SOXL","price":31.5,"quote_timestamp":ts,"trading_date":"2026-08-04","provider":provider,"source_type":"LIVE_QUOTE","confidence":.95,"warnings":[]}

def history(provider="ROBINHOOD_MCP", dates=("2026-08-03","2026-08-04")):
    return {"symbol":"SOXL","interval":"1d","period":"1mo","provider":provider,"generated_at":NOW.isoformat(),"corporate_action_adjusted":False,"split_history":[],"dividend_history":[],"warnings":[],"bars":[{"date":d,"open":30,"high":32,"low":29,"close":31,"adjusted_close":None,"volume":100} for d in dates]}

def provider(tmp_path, sources):
    return EnterpriseMarketDataProvider(sources, tmp_path/"results", tmp_path/"cache", FreshnessPolicy(), lambda: NOW)

def test_robinhood_preferred(tmp_path): assert provider(tmp_path,[Source("ROBINHOOD_MCP",quote=quote()),Source("YFINANCE",quote=quote("YFINANCE"))]).get_quote("SOXL")["provider"] == "ROBINHOOD_MCP"
def test_yfinance_fallback(tmp_path): assert provider(tmp_path,[Source("ROBINHOOD_MCP",error=RuntimeError("down")),Source("YFINANCE",quote=quote("YFINANCE"))]).get_quote("SOXL")["provider"] == "YFINANCE"
def test_stooq_fallback(tmp_path): assert provider(tmp_path,[Source("ROBINHOOD_MCP",error=RuntimeError()),Source("YFINANCE",error=RuntimeError()),Source("STOOQ",quote=quote("STOOQ"))]).get_quote("SOXL")["provider"] == "STOOQ"
def test_fresh_cache_fallback(tmp_path): assert provider(tmp_path,[Source("ROBINHOOD_MCP",error=RuntimeError()),Source("LOCAL_CACHE",quote=quote("LOCAL_CACHE"))]).get_quote("SOXL")["cache_used"] is True
def test_stale_cache_rejected(tmp_path):
    with pytest.raises(MarketDataUnavailable): provider(tmp_path,[Source("LOCAL_CACHE",quote=quote("LOCAL_CACHE","2026-06-22T20:00:00+00:00"))]).get_quote("SOXL")
def test_no_source_safe_failure(tmp_path):
    with pytest.raises(MarketDataUnavailable): provider(tmp_path,[Source("ROBINHOOD_MCP",error=RuntimeError("down"))]).get_quote("SOXL")
def test_required_failure_strategy_scoped(tmp_path):
    result=provider(tmp_path,[Source("ROBINHOOD_MCP",error=RuntimeError("down"))]).refresh_strategy("SWING-001",["SOXL"],[]); assert result["status"]=="BLOCKED" and result["strategy_id"]=="SWING-001"
def test_optional_failure_warning(tmp_path):
    result=provider(tmp_path,[Source("ROBINHOOD_MCP",error=RuntimeError("down"))]).refresh_strategy("SWING-001",[],["TQQQ"]); assert result["status"]=="WARNING" and not result["errors"]
def test_contract_and_timestamps_preserved(tmp_path):
    p=provider(tmp_path,[Source("ROBINHOOD_MCP",quote=quote())]); data=p.get_quote("SOXL"); assert data["quote_timestamp"]=="2026-08-04T16:59:00+00:00"; assert (tmp_path/"results/enterprise_market_data_contract.json").is_file()
def test_duplicate_conflicting_bars_rejected(tmp_path):
    bad=history(); bad["bars"].append({**bad["bars"][-1],"close":30})
    with pytest.raises(MarketDataUnavailable): provider(tmp_path,[Source("ROBINHOOD_MCP",history=bad)]).get_history("SOXL")
def test_adjusted_close_and_split_metadata(tmp_path):
    raw=history(); raw["bars"][-1]["adjusted_close"]=30.5; raw["split_history"]=[{"date":"2026-01-01","ratio":2}]
    result=provider(tmp_path,[Source("ROBINHOOD_MCP",history=raw)]).get_history("SOXL"); assert result["bars"][-1]["adjusted_close"]==30.5 and result["split_history"]
def test_evidence_has_no_authentication_data(tmp_path):
    p=provider(tmp_path,[Source("ROBINHOOD_MCP",quote=quote())]); p.get_quote("SOXL")
    text="".join(x.read_text() for x in (tmp_path/"results").iterdir()); assert "oauth" not in text.lower() and "token" not in text.lower()
def test_atomic_writes_leave_no_temp_files(tmp_path):
    p=provider(tmp_path,[Source("ROBINHOOD_MCP",quote=quote())]); p.get_quote("SOXL"); assert not list((tmp_path/"results").glob(".*"))
def test_no_capital_allocation_fields(tmp_path):
    p=provider(tmp_path,[Source("ROBINHOOD_MCP",quote=quote())]); p.get_quote("SOXL")
    status=json.loads((tmp_path/"results/enterprise_market_data_status.json").read_text()); assert "allocation" not in json.dumps(status).lower()
def test_provider_health_reporting(tmp_path):
    p=provider(tmp_path,[Source("ROBINHOOD_MCP",quote=quote())]); p.get_quote("SOXL")
    health=json.loads((tmp_path/"results/enterprise_market_data_provider_health.json").read_text()); assert health["healthy"] is True and health["safety"]["read_only"] is True
