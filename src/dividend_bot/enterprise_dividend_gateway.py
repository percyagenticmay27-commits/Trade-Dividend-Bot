"""Dividend income eligibility gateway between shared Discovery and Dividend Watchlist.

The gateway is strategy-specific. It never changes shared Discovery and never
activates a paper position. It evaluates reviewed income-mapping evidence and
fails closed when the income mechanism is missing, immature, inactive, or below
the governed completed-calendar-month income target.

Gateway income qualification is deliberately monthly. Annual or trailing-365-day
distribution yield is not used for admission. Refreshed suitability evidence
publishes actual completed-month distribution income for the reviewed vehicle.

Maturity uses the existing suitability evidence measurement ``fund_age_days``.
The governed minimum is 60 days. Evidence freshness is supplied by upstream
reviewed evidence state; this module does not invent an hourly TTL.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

INCOME_TARGET_MONTHLY_PERCENT = 1.0
MINIMUM_FUND_AGE_DAYS = 60
INCOME_MAPPING_PATH = Path("results/enterprise_dividend_income_mapping.json")
SUITABILITY_EVIDENCE_PATH = Path("inputs/dividend_suitability_evidence.json")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _records(value: Any):
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _records(child)


def _symbol(record: Mapping[str, Any]) -> str:
    return str(record.get("underlying_symbol") or record.get("symbol") or record.get("ticker") or "").strip().upper()


def _find_mapping(payload: Any, symbol: str) -> Mapping[str, Any]:
    for record in _records(payload):
        if _symbol(record) == symbol.upper():
            return record
    return {}


def _find_vehicle_evidence(payload: Any, income_symbol: str) -> Mapping[str, Any]:
    target = income_symbol.strip().upper()
    if not target:
        return {}
    for record in _records(payload):
        if str(record.get("income_symbol") or "").strip().upper() == target:
            return record
    return {}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _evidence_as_of(mapping: Mapping[str, Any]) -> Any:
    for key in ("evidence_as_of", "generated_at_utc", "updated_at_utc", "as_of"):
        if mapping.get(key) not in (None, ""):
            return mapping.get(key)
    evidence = mapping.get("mapping_evidence")
    if isinstance(evidence, list):
        dated = [
            record.get(key)
            for record in evidence
            if isinstance(record, Mapping)
            for key in ("evidence_as_of", "published_at", "generated_at_utc", "as_of")
            if record.get(key) not in (None, "")
        ]
        if dated:
            return dated[-1]
    return None


def _freshness_status(mapping: Mapping[str, Any]) -> str:
    """Honor reviewed upstream freshness state; never invent an hourly TTL."""
    explicit = str(mapping.get("freshness_status") or "").strip().upper()
    if explicit in {"FRESH", "CURRENT", "PASS"}:
        return "FRESH"
    if explicit in {"STALE", "STALE_OR_UNAVAILABLE", "UNAVAILABLE", "FAIL"}:
        return "STALE_OR_UNAVAILABLE"
    if mapping.get("is_stale") is False:
        return "FRESH"
    if mapping.get("is_stale") is True:
        return "STALE_OR_UNAVAILABLE"
    return "UNVERIFIED"


def evaluate_dividend_gateway(
    symbol: str,
    root: str | Path = ".",
    *,
    mapping: Mapping[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Evaluate one underlying using reviewed mapping plus refreshed vehicle evidence."""
    del now  # retained for call-site compatibility; no arbitrary time TTL is used.
    root_path = Path(root)
    source = mapping if isinstance(mapping, Mapping) else _find_mapping(_load_json(root_path / INCOME_MAPPING_PATH), symbol)
    source = dict(source) if isinstance(source, Mapping) else {}

    # Explicit caller-supplied mappings remain authoritative for unit/integration
    # callers. Normal runtime evaluation enriches the reviewed mapping with the
    # latest suitability vehicle evidence produced by the scheduled refresh.
    if mapping is None and source.get("income_symbol"):
        refreshed = _find_vehicle_evidence(
            _load_json(root_path / SUITABILITY_EVIDENCE_PATH), str(source.get("income_symbol"))
        )
        if refreshed:
            source.update(dict(refreshed))

    income_symbol = source.get("income_symbol")
    mechanism = source.get("income_mechanism")
    frequency = str(source.get("distribution_frequency") or "").strip().upper()
    observed = _number(source.get("observed_income_monthly_percent"))
    if observed is None:
        observed = _number(source.get("monthly_equivalent_income_percent"))
    fund_age_days = _number(source.get("fund_age_days"))
    vehicle_status = str(source.get("vehicle_status") or "").strip().upper()
    mapping_status = str(source.get("mapping_status") or "").strip().upper()
    evidence_as_of = _evidence_as_of(source)
    freshness_status = _freshness_status(source)

    reasons: list[str] = []
    if not source:
        reasons.append("No reviewed Dividend income mapping is available.")
    if not income_symbol:
        reasons.append("No income vehicle is mapped to the underlying.")
    if not mechanism:
        reasons.append("No reviewed income mechanism is available.")
    if frequency not in {"WEEKLY", "MONTHLY"}:
        reasons.append("Distribution frequency is not a reviewed weekly or monthly mechanism.")
    if observed is None:
        reasons.append("Completed-calendar-month income evidence is unavailable.")
    elif observed < INCOME_TARGET_MONTHLY_PERCENT:
        reasons.append(f"Observed monthly income {observed:.4g}% is below the {INCOME_TARGET_MONTHLY_PERCENT:.4g}% minimum.")
    if fund_age_days is None:
        reasons.append("Reviewed fund_age_days evidence is unavailable.")
    elif fund_age_days < MINIMUM_FUND_AGE_DAYS:
        reasons.append(f"Income mechanism age {fund_age_days:.4g} days is below the {MINIMUM_FUND_AGE_DAYS}-day minimum.")
    if vehicle_status in {"DELISTED", "LIQUIDATED", "TERMINATED", "INACTIVE", "CLOSED"}:
        reasons.append(f"Income vehicle status is {vehicle_status}.")
    elif vehicle_status not in {"ACTIVE", "TRADABLE"}:
        reasons.append("Current reviewed vehicle-active evidence is unavailable.")
    if mapping_status in {"DISQUALIFIED", "REJECTED", "INVALID", "RESEARCH_REQUIRED"}:
        reasons.append(f"Income mapping status is {mapping_status}.")
    if freshness_status != "FRESH":
        reasons.append("Current reviewed income evidence freshness is unavailable or stale.")

    qualified = not reasons
    status = "QUALIFIED" if qualified else "DISQUALIFIED"
    if reasons and (not source or any("unavailable" in reason.lower() for reason in reasons)):
        status = "RESEARCH_REQUIRED"

    return {
        "underlying_symbol": symbol.upper(),
        "income_symbol": income_symbol,
        "income_mechanism": mechanism,
        "distribution_frequency": frequency or None,
        "income_target_monthly_percent": INCOME_TARGET_MONTHLY_PERCENT,
        "observed_income_monthly_percent": observed,
        "observed_income_month": source.get("observed_income_month"),
        "monthly_income_method": source.get("monthly_income_method"),
        "fund_age_days": fund_age_days,
        "minimum_fund_age_days": MINIMUM_FUND_AGE_DAYS,
        "vehicle_status": vehicle_status or None,
        "mapping_status": mapping_status or None,
        "evidence_as_of": evidence_as_of,
        "freshness_status": freshness_status,
        "eligibility_status": status,
        "watchlist_admission_allowed": qualified,
        "manual_review_required": True,
        "automatic_activation_allowed": False,
        "reasons": reasons,
        "policy": "DIVIDEND_GATEWAY_MONTHLY_INCOME_AND_AGE_FAIL_CLOSED",
    }


def apply_dividend_gateway_to_watchlist(
    row: Mapping[str, Any], root: str | Path = ".", *, now: Any = None
) -> dict[str, Any]:
    """Admit only currently qualified mappings to the Dividend Watchlist.

    Existing held paper positions are retained in the row for lifecycle review;
    gateway failure never auto-sells a position. Non-held unqualified candidates
    are excluded from the actionable Watchlist and retained in
    ``dividend_gateway_research`` for monitoring/audit.
    """
    result = copy.deepcopy(dict(row))
    raw = result.get("watchlist")
    if not isinstance(raw, list):
        return result

    admitted: list[Any] = []
    research: list[dict[str, Any]] = []
    for value in raw:
        if not isinstance(value, Mapping):
            continue
        item = copy.deepcopy(dict(value))
        symbol = _symbol(item)
        gateway = evaluate_dividend_gateway(symbol, root, now=now)
        item["dividend_gateway"] = gateway
        if gateway["watchlist_admission_allowed"]:
            admitted.append(item)
        elif item.get("currently_held") is True:
            item["gateway_lifecycle_review_required"] = True
            admitted.append(item)
            research.append({"underlying_symbol": symbol, "status": gateway["eligibility_status"], "held_position": True, "reasons": gateway["reasons"]})
        else:
            research.append({"underlying_symbol": symbol, "status": gateway["eligibility_status"], "held_position": False, "reasons": gateway["reasons"]})

    result["watchlist"] = admitted
    result["watchlist_count"] = len(admitted)
    result["dividend_gateway_research"] = research
    result["dividend_gateway_policy"] = "DIVIDEND_GATEWAY_MONTHLY_INCOME_AND_AGE_FAIL_CLOSED"
    return result
