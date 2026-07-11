"""Unbiased candidate discovery for Trade-Dividend-Bot Version 2.

Builds a normalized single-instrument universe from existing paper-portfolio,
watchlist, ranking, market-data, and user-configured artifacts. This module only
prepares candidates for later evidence refresh and Capital Efficiency scoring.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

MODULE_NAME = "candidate_discovery_engine"
MODULE_VERSION = "2.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True
OPTIMIZATION_PROFILE = "MAXIMUM_TOTAL_WEALTH"

DEFAULT_OUTPUT_FILES = {
    "json": "candidate_discovery.json",
    "csv": "candidate_discovery.csv",
    "markdown": "candidate_discovery.md",
}

DEFAULT_SOURCE_FILES = {
    "MARKET_SNAPSHOT": "market_data_snapshot.json",
    "PORTFOLIO": "portfolio_lifecycle_report.json",
    "PORTFOLIO_ALLOCATION": "capital_allocation_report.json",
    "WATCHLIST": "watchlist_report.json",
    "DIVIDEND_RANKING": "dividend_rankings.json",
    "OPPORTUNITY_PAIRING": "opportunity_pairing_report.json",
    "PORTFOLIO_DECISION": "portfolio_decision_report.json",
    "USER_UNIVERSE": "candidate_universe.json",
}

SYMBOL_KEYS = {
    "symbol", "ticker", "asset", "instrument", "underlying_symbol",
    "income_symbol", "growth_symbol", "reserve_symbol",
}
SYMBOL_LIST_KEYS = {
    "symbols", "tickers", "holdings", "watchlist", "candidates", "universe",
    "portfolio_symbols", "candidate_symbols", "pair_symbols",
}


@dataclass(frozen=True)
class DiscoveredCandidate:
    symbol: str
    candidate_id: str
    candidate_type: str
    sources: list[str]
    source_files: list[str]
    currently_held: bool
    on_watchlist: bool
    has_market_data: bool
    market_data_stale: bool
    eligible_for_refresh: bool
    status: str
    warnings: list[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_symbol(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper()
    if not symbol or len(symbol) > 15:
        return None
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-^")
    if any(character not in allowed for character in symbol):
        return None
    if symbol in {"UNKNOWN", "NONE", "N/A", "NA", "CASH"}:
        return None
    return symbol


def _extract_symbols(value: Any, parent_key: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if key_text in SYMBOL_KEYS:
                symbol = _normalize_symbol(child)
                if symbol:
                    found.add(symbol)
            elif key_text in SYMBOL_LIST_KEYS:
                found.update(_extract_symbols(child, key_text))
            elif isinstance(child, (Mapping, list, tuple, set)):
                found.update(_extract_symbols(child, key_text))
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            if isinstance(child, str) and parent_key in SYMBOL_LIST_KEYS:
                symbol = _normalize_symbol(child)
                if symbol:
                    found.add(symbol)
            else:
                found.update(_extract_symbols(child, parent_key))
    elif isinstance(value, str) and parent_key in SYMBOL_LIST_KEYS:
        symbol = _normalize_symbol(value)
        if symbol:
            found.add(symbol)
    return found


def _load_json(path: Path) -> tuple[Optional[Any], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Could not read {path.name}: {exc}"


def _market_record_map(payload: Any) -> dict[str, Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return {}
    records: Any = []
    for key in ("records", "market_records", "data", "results", "symbols"):
        if isinstance(payload.get(key), list):
            records = payload[key]
            break
    result: dict[str, Mapping[str, Any]] = {}
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, Mapping):
            continue
        symbol = _normalize_symbol(record.get("symbol") or record.get("ticker"))
        if symbol:
            result[symbol] = record
    return result


def discover_candidates(
    source_payloads: Mapping[str, Any],
    source_files: Optional[Mapping[str, str]] = None,
    explicit_symbols: Optional[Iterable[str]] = None,
) -> list[dict[str, Any]]:
    if not isinstance(source_payloads, Mapping):
        raise ValueError("source_payloads must be a mapping")

    files = dict(source_files or {})
    by_symbol: dict[str, dict[str, Any]] = {}
    market_records = _market_record_map(source_payloads.get("MARKET_SNAPSHOT"))

    def register(symbol: str, source: str) -> None:
        entry = by_symbol.setdefault(symbol, {"sources": set(), "source_files": set()})
        entry["sources"].add(source)
        if files.get(source):
            entry["source_files"].add(files[source])

    for source, payload in source_payloads.items():
        for symbol in _extract_symbols(payload):
            register(symbol, str(source).upper())

    for raw_symbol in explicit_symbols or []:
        symbol = _normalize_symbol(raw_symbol)
        if symbol:
            register(symbol, "EXPLICIT")

    candidates: list[dict[str, Any]] = []
    for symbol in sorted(by_symbol):
        meta = by_symbol[symbol]
        sources = sorted(meta["sources"])
        record = market_records.get(symbol)
        has_market_data = record is not None
        stale = bool(record.get("is_stale")) if record else False
        held = bool({"PORTFOLIO", "PORTFOLIO_ALLOCATION", "PORTFOLIO_DECISION"} & set(sources))
        watched = "WATCHLIST" in sources
        warnings: list[str] = []
        if not has_market_data:
            warnings.append("Market evidence must be refreshed before scoring.")
        elif stale:
            warnings.append("Market evidence is stale and should be refreshed.")
        status = "READY_FOR_SCORING" if has_market_data and not stale else "READY_FOR_REFRESH"
        candidate = DiscoveredCandidate(
            symbol=symbol,
            candidate_id=symbol,
            candidate_type="SINGLE_INSTRUMENT",
            sources=sources,
            source_files=sorted(meta["source_files"]),
            currently_held=held,
            on_watchlist=watched,
            has_market_data=has_market_data,
            market_data_stale=stale,
            eligible_for_refresh=True,
            status=status,
            warnings=warnings,
        )
        candidates.append(asdict(candidate))
    return candidates


def build_candidate_discovery_report(
    source_payloads: Mapping[str, Any],
    source_files: Optional[Mapping[str, str]] = None,
    explicit_symbols: Optional[Iterable[str]] = None,
    load_warnings: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    candidates = discover_candidates(source_payloads, source_files, explicit_symbols)
    ready = sum(1 for item in candidates if item["status"] == "READY_FOR_SCORING")
    refresh = sum(1 for item in candidates if item["status"] == "READY_FOR_REFRESH")
    held = sum(1 for item in candidates if item["currently_held"])
    watched = sum(1 for item in candidates if item["on_watchlist"])
    warnings = list(load_warnings or [])
    if not candidates:
        warnings.append("No symbols were discovered from the available artifacts.")
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "optimization_profile": OPTIMIZATION_PROFILE,
        "candidate_count": len(candidates),
        "ready_for_scoring_count": ready,
        "ready_for_refresh_count": refresh,
        "currently_held_count": held,
        "watchlist_count": watched,
        "symbols": [item["symbol"] for item in candidates],
        "candidates": candidates,
        "warnings": warnings,
        "errors": [],
        "safety_guarantees": [
            "paper_trade_mode is enforced as True",
            "live_trading_enabled is enforced as False",
            "broker_execution_enabled is enforced as False",
            "discovery does not favor any ticker, sector, or instrument style",
            "all discovered candidates require evidence-based scoring",
        ],
    }


def format_candidate_discovery_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Candidate Discovery",
        "",
        f"- Optimization Profile: {payload.get('optimization_profile', OPTIMIZATION_PROFILE)}",
        f"- Candidates: {payload.get('candidate_count', 0)}",
        f"- Ready for Scoring: {payload.get('ready_for_scoring_count', 0)}",
        f"- Ready for Refresh: {payload.get('ready_for_refresh_count', 0)}",
        f"- Current Holdings: {payload.get('currently_held_count', 0)}",
        f"- Watchlist Candidates: {payload.get('watchlist_count', 0)}",
        "",
        "## Candidate Universe",
        "",
        "| Symbol | Status | Held | Watchlist | Sources |",
        "|---|---|---:|---:|---|",
    ]
    candidates = payload.get("candidates", [])
    if not candidates:
        lines.append("| None | - | - | - | - |")
    for item in candidates:
        lines.append(
            f"| {item.get('symbol')} | {item.get('status')} | "
            f"{'Yes' if item.get('currently_held') else 'No'} | "
            f"{'Yes' if item.get('on_watchlist') else 'No'} | "
            f"{', '.join(item.get('sources', []))} |"
        )
    if payload.get("warnings"):
        lines.extend(["", "## Warnings", *(f"- {warning}" for warning in payload["warnings"])])
    return "\n".join(lines) + "\n"


def write_candidate_discovery(
    root_path: str = ".",
    source_files: Optional[Mapping[str, str]] = None,
    explicit_symbols: Optional[Iterable[str]] = None,
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    root = Path(root_path)
    files = dict(DEFAULT_SOURCE_FILES)
    if source_files:
        files.update(source_files)
    payloads: dict[str, Any] = {}
    warnings: list[str] = []
    for source, filename in files.items():
        payload, warning = _load_json(root / filename)
        if payload is not None:
            payloads[source] = payload
        if warning:
            warnings.append(warning)
    report = build_candidate_discovery_report(payloads, files, explicit_symbols, warnings)

    outputs = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        outputs.update(output_files)
    (root / outputs["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / outputs["markdown"]).write_text(format_candidate_discovery_markdown(report), encoding="utf-8")
    with (root / outputs["csv"]).open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "symbol", "candidate_type", "status", "currently_held", "on_watchlist",
            "has_market_data", "market_data_stale", "sources", "source_files",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in report["candidates"]:
            writer.writerow({
                "symbol": item["symbol"],
                "candidate_type": item["candidate_type"],
                "status": item["status"],
                "currently_held": item["currently_held"],
                "on_watchlist": item["on_watchlist"],
                "has_market_data": item["has_market_data"],
                "market_data_stale": item["market_data_stale"],
                "sources": "|".join(item["sources"]),
                "source_files": "|".join(item["source_files"]),
            })
    return report


if __name__ == "__main__":
    result = write_candidate_discovery()
    print(f"Candidate Discovery: {result['candidate_count']} candidate(s)")
