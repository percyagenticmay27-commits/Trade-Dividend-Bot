"""Shared read-only market-data refresh engine for the Dividend Bot.

The engine discovers symbols from portfolio, paper-history, watchlist artifacts,
and configured Dividend strategy evidence, refreshes each symbol once through the
central MarketDataService, and writes one normalized JSON/CSV snapshot for
downstream scoring. Provider data is read-only.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from market_data_provider import MarketDataService
from paper_portfolio_config import PAPER_PAIRS
from yahoo_finance_provider import MarketDataProviderError

MODULE_NAME = "market_data_integration_engine"
MODULE_VERSION = "1.3.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
READ_ONLY_MARKET_DATA = True

DEFAULT_OUTPUT_FILES = {"json": "market_data_snapshot.json", "csv": "market_data_snapshot.csv"}
DEFAULT_SYMBOL_FILES = [
    "portfolio_lifecycle_report.json", "portfolio_construction_report.json",
    "capital_allocation_report.json", "portfolio_decision_report.json",
    "opportunity_pairing_report.json", "dividend_rankings.json", "watchlist.json",
    "portfolio.json", "paper_state.json", "paper_trade_log.csv", "paper_signal_history.csv",
]
SYMBOL_KEYS = {"symbol", "ticker", "income_symbol", "growth_symbol", "primary_symbol", "secondary_symbol", "asset", "security"}
CSV_SYMBOL_HEADERS = ("symbol", "ticker", "income_symbol", "growth_symbol", "primary_symbol", "secondary_symbol", "Symbol", "Ticker")

@dataclass(frozen=True)
class MarketDataIntegrationReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    read_only_market_data: bool
    status: str
    symbol_count: int
    successful_symbol_count: int
    failed_symbol_count: int
    symbols: list[str]
    records: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]

def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _normalize_symbol(value: Any) -> Optional[str]:
    if not isinstance(value, str): return None
    symbol = value.strip().upper()
    return symbol if symbol and len(symbol) <= 20 else None

def configured_strategy_market_symbols() -> list[str]:
    """Return configured traded, signal, and earnings evidence symbols."""
    symbols: set[str] = set()
    for config in PAPER_PAIRS.values():
        for key in ("a", "b", "a_signal", "b_signal", "earnings_source"):
            symbol = _normalize_symbol(config.get(key))
            if symbol: symbols.add(symbol)
    return sorted(symbols)

def _collect_symbols(value: Any, result: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in SYMBOL_KEYS:
                symbol = _normalize_symbol(item)
                if symbol: result.add(symbol)
            _collect_symbols(item, result)
    elif isinstance(value, list):
        for item in value: _collect_symbols(item, result)

def _collect_csv_symbols(path: Path, result: set[str]) -> None:
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for key in CSV_SYMBOL_HEADERS:
                    symbol = _normalize_symbol(row.get(key))
                    if symbol: result.add(symbol)
    except (OSError, UnicodeError, csv.Error): return

def discover_market_symbols(root_path: str = ".", explicit_symbols: Optional[Iterable[str]] = None, symbol_files: Optional[Iterable[str]] = None) -> list[str]:
    symbols: set[str] = set(configured_strategy_market_symbols())
    for value in explicit_symbols or []:
        symbol = _normalize_symbol(value)
        if symbol: symbols.add(symbol)
    root = Path(root_path)
    for filename in symbol_files or DEFAULT_SYMBOL_FILES:
        path = root / filename
        if not path.exists(): continue
        if path.suffix.lower() == ".csv":
            _collect_csv_symbols(path, symbols); continue
        if path.suffix.lower() != ".json": continue
        try: payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError): continue
        _collect_symbols(payload, symbols)
    return sorted(symbols)

def _safe_number(value: Any) -> float:
    if isinstance(value, bool): return 0.0
    try: return round(float(value), 6)
    except (TypeError, ValueError): return 0.0

def _optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool): return None
    try: return float(value)
    except (TypeError, ValueError): return None

def _history_rows(history: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = history.get("rows") or history.get("history") or history.get("prices") or history.get("records") or []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []

def _latest_history_close(history: Mapping[str, Any]) -> float:
    rows = _history_rows(history)
    return _safe_number(rows[-1].get("close", rows[-1].get("Close", 0.0))) if rows else 0.0

def _dividend_rows(dividends: Mapping[str, Any]) -> list[Any]:
    rows = dividends.get("payments") or dividends.get("dividends") or dividends.get("history") or dividends.get("records") or []
    return rows if isinstance(rows, list) else []

def _dividend_summary(dividends: Mapping[str, Any]) -> tuple[int, float]:
    rows = _dividend_rows(dividends); total = 0.0
    for row in rows:
        value = row.get("dividend", row.get("amount", row.get("value", 0.0))) if isinstance(row, Mapping) else row
        total += _safe_number(value)
    return len(rows), round(total, 6)

def _year_from_date(value: Any) -> int | None:
    text = str(value or "")
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else None

def _derived_dividend_growth(dividends: Mapping[str, Any]) -> float | None:
    annual: dict[int, float] = {}
    for row in _dividend_rows(dividends):
        if not isinstance(row, Mapping): continue
        year = _year_from_date(row.get("date")); amount = _safe_number(row.get("amount", row.get("dividend", row.get("value", 0.0))))
        if year is not None and amount > 0: annual[year] = annual.get(year, 0.0) + amount
    years = sorted(year for year, amount in annual.items() if amount > 0)
    if len(years) < 2: return None
    latest, prior = years[-1], years[-2]
    return round((annual[latest] / annual[prior]) - 1.0, 6) if annual[prior] > 0 else None

def _normalized_income_fields(quote: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    name = quote.get("short_name") or quote.get("long_name") or quote.get("name")
    if name not in (None, ""): result["name"] = str(name)
    yield_ratio = _optional_number(quote.get("dividend_yield"))
    if yield_ratio is not None and yield_ratio >= 0: result["dividend_yield_percent"] = round(yield_ratio * 100.0, 6)
    annual_rate = _optional_number(quote.get("dividend_rate"))
    if annual_rate is not None and annual_rate >= 0: result["annual_dividend_rate"] = round(annual_rate, 6)
    ex_date = quote.get("ex_dividend_date") or quote.get("next_ex_dividend_date")
    if ex_date not in (None, ""): result["next_ex_dividend_date"] = str(ex_date)
    if result: result["income_normalization_source"] = str(quote.get("provider") or quote.get("data_source") or "MARKET_PROVIDER")
    return result

def refresh_market_data_snapshot(symbols: Iterable[str], service: MarketDataService, force_refresh: bool = False, history_period: str = "1y", history_interval: str = "1d", dividend_period: str = "5y") -> dict[str, Any]:
    normalized = sorted({symbol for raw in symbols if (symbol := _normalize_symbol(raw))}); records=[]; warnings=[]; errors=[]
    for symbol in normalized:
        try:
            quote = service.get_quote(symbol, force_refresh=force_refresh)
            history = service.get_history(symbol, period=history_period, interval=history_interval, force_refresh=force_refresh)
            dividends = service.get_dividends(symbol, period=dividend_period, force_refresh=force_refresh)
            dividend_count, dividend_total = _dividend_summary(dividends); derived_growth = _derived_dividend_growth(dividends); enriched_quote = dict(quote)
            if enriched_quote.get("dividend_growth") is None and derived_growth is not None:
                enriched_quote["dividend_growth"] = derived_growth; enriched_quote["dividend_growth_source"] = "DERIVED_ANNUAL_PAYMENT_HISTORY"
            price = _safe_number(enriched_quote.get("price", enriched_quote.get("regular_market_price", enriched_quote.get("current_price", 0.0))))
            if price == 0.0: price = _latest_history_close(history)
            record = {"symbol":symbol,"price":price,"previous_close":_safe_number(enriched_quote.get("previous_close",0.0)),"market_cap":_safe_number(enriched_quote.get("market_cap",0.0)),"dividend_yield":_safe_number(enriched_quote.get("dividend_yield",0.0)),"beta":_safe_number(enriched_quote.get("beta",enriched_quote.get("beta_3y",0.0))),"volume":_safe_number(enriched_quote.get("volume",0.0)),"fifty_two_week_high":_safe_number(enriched_quote.get("fifty_two_week_high",0.0)),"fifty_two_week_low":_safe_number(enriched_quote.get("fifty_two_week_low",0.0)),"sector":str(enriched_quote.get("sector") or "UNKNOWN"),"industry":str(enriched_quote.get("industry") or enriched_quote.get("category") or "UNKNOWN"),"quote_type":str(enriched_quote.get("quote_type") or "UNKNOWN"),"dividend_record_count":dividend_count,"dividend_total":dividend_total,"derived_dividend_growth":derived_growth,"history_row_count":len(_history_rows(history)),"quote_source":str(enriched_quote.get("data_source","UNKNOWN")),"history_source":str(history.get("data_source","UNKNOWN")),"dividend_source":str(dividends.get("data_source","UNKNOWN")),"is_stale":bool(enriched_quote.get("is_stale") or history.get("is_stale") or dividends.get("is_stale")),"quote":enriched_quote,"history":dict(history),"dividends":dict(dividends)}
            record.update(_normalized_income_fields(enriched_quote)); records.append(record)
        except (MarketDataProviderError, OSError, RuntimeError, TypeError, ValueError) as exc: errors.append(f"{symbol}: {exc}")
    if not normalized: warnings.append("No portfolio or watchlist symbols were discovered; provider access was skipped.")
    stale_count = sum(1 for row in records if row["is_stale"])
    if stale_count: warnings.append(f"{stale_count} symbol records used stale cached data.")
    status = "ERROR" if normalized and not records else ("PARTIAL" if errors or not normalized else "COMPLETE")
    payload = asdict(MarketDataIntegrationReport(MODULE_NAME,MODULE_VERSION,SCHEMA_VERSION,_now(),True,False,False,True,status,len(normalized),len(records),len(errors),normalized,records,warnings,errors))
    validate_market_data_snapshot(payload); return payload

def validate_market_data_snapshot(payload: Any) -> bool:
    if not isinstance(payload, Mapping): raise ValueError("payload must be a mapping")
    required = set(MarketDataIntegrationReport.__dataclass_fields__); missing = sorted(required - set(payload))
    if missing: raise ValueError(f"missing required fields: {', '.join(missing)}")
    for field, expected in {"paper_trade_mode":True,"live_trading_enabled":False,"broker_execution_enabled":False,"read_only_market_data":True}.items():
        if payload[field] is not expected: raise ValueError(f"{field} must be {expected}")
    if payload["status"] not in {"COMPLETE","PARTIAL","ERROR"}: raise ValueError("unsupported status")
    for field in ["symbol_count","successful_symbol_count","failed_symbol_count"]:
        if not isinstance(payload[field],int) or isinstance(payload[field],bool) or payload[field] < 0: raise ValueError(f"{field} must be a non-negative integer")
    if payload["successful_symbol_count"] + payload["failed_symbol_count"] != payload["symbol_count"]: raise ValueError("successful and failed counts must total symbol_count")
    for field in ["symbols","records","warnings","errors"]:
        if not isinstance(payload[field],list): raise ValueError(f"{field} must be a list")
    return True

def write_market_data_snapshot(root_path: str = ".", symbols: Optional[Iterable[str]] = None, service: Optional[MarketDataService] = None, force_refresh: bool = False, output_files: Optional[Mapping[str,str]] = None, symbol_files: Optional[Iterable[str]] = None) -> dict[str,Any]:
    root = Path(root_path); root.mkdir(parents=True,exist_ok=True); files = dict(DEFAULT_OUTPUT_FILES)
    if output_files: files.update(output_files)
    discovered = discover_market_symbols(root_path,symbols,symbol_files); active_service = service or MarketDataService(root_path=root_path); payload = refresh_market_data_snapshot(discovered,active_service,force_refresh=force_refresh)
    (root/files["json"]).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    fieldnames = ["symbol","name","price","previous_close","market_cap","dividend_yield","dividend_yield_percent","annual_dividend_rate","next_ex_dividend_date","beta","volume","fifty_two_week_high","fifty_two_week_low","sector","industry","quote_type","dividend_record_count","dividend_total","derived_dividend_growth","history_row_count","quote_source","history_source","dividend_source","income_normalization_source","is_stale"]
    with (root/files["csv"]).open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fieldnames); writer.writeheader()
        for row in payload["records"]: writer.writerow({name:row.get(name,"") for name in fieldnames})
    return payload

if __name__ == "__main__":
    report=write_market_data_snapshot(); print(f"Market Data Integration: {report['status']} ({report['successful_symbol_count']}/{report['symbol_count']})")
