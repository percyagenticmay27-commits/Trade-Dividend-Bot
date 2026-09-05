"""Dividend income eligibility gateway between shared Discovery and Dividend Watchlist.

The gateway is strategy-specific.  It never changes shared Discovery and never
activates a paper position.  It evaluates current reviewed income-mapping
evidence and fails closed when evidence is missing, stale, immature, inactive,
or below the governed income target.

Income measurement is intentionally not invented here: upstream reviewed
mapping evidence must publish ``observed_income_monthly_percent`` (or the
explicit alias ``monthly_equivalent_income_percent``).  Likewise, maturity is
accepted only from an explicit age value in months, or from a reviewed
``maturity_status``.  This avoids silently redefining the user's "two months"
policy as an arbitrary number of days.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

INCOME_TARGET_MONTHLY_PERCENT = 1.0
MINIMUM_MECHANISM_AGE_MONTHS = 2.0
MAPPING_EVIDENCE_MAX_AGE_HOURS = 168.0
INCOME_MAPPING_PATH = Path("results/enterprise_dividend_income_mapping.json")


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


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _evidence_as_of(mapping: Mapping[str, Any]) -> Any:
    for key in ("evidence_as_of", "generated_at_utc", "updated_at_utc", "as_of"):
        if mapping.get(key) not in (None, ""):
            return mapping.get(key)
    evidence = mapping.get("mapping_evidence")
    if isinstance(evidence, list):
        dated: list[tuple[datetime, Any]] = []
        for record in evidence:
            if not isinstance(record, Mapping):
                continue
            for key in ("evidence_as_of", "published_at", "generated_at_utc", "as_of"):
                raw = record.get(key)
                parsed = _timestamp(raw)
                if parsed is not None:
                    dated.append((parsed, raw))
                    break
        if dated:
            return max(dated, key=lambda pair: pair[0])[1]
    return None


def _is_fresh(raw: Any, now: datetime | None) -> tuple[bool, float | None]:
    parsed = _timestamp(raw)
    if parsed is None:
        return False, None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age = max(0.0, (current.astimezone(timezone.utc) - parsed).total_seconds() / 3600.0)
    return age <= MAPPING_EVIDENCE_MAX_AGE_HOURS, age


def evaluate_dividend_gateway(
    symbol: str,
    root: str | Path = ".",
    *,
    mapping: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate one underlying using current reviewed income-mapping evidence."""
    root_path = Path(root)
    source = mapping if isinstance(mapping, Mapping) else _find_mapping(_load_json(root_path / INCOME_MAPPING_PATH), symbol)
    source = source if isinstance(source, Mapping) else {}

    income_symbol = source.get("income_symbol")
    mechanism = source.get("income_mechanism")
    frequency = str(source.get("distribution_frequency") or "").strip().upper()
    observed = _number(source.get("observed_income_monthly_percent"))
    if observed is None:
        observed = _number(source.get("monthly_equivalent_income_percent"))
    age_months = _number(source.get("mechanism_age_months"))
    maturity_status = str(source.get("maturity_status") or "").strip().upper()
    vehicle_status = str(source.get("vehicle_status") or "").strip().upper()
    mapping_status = str(source.get("mapping_status") or "").strip().upper()
    evidence_as_of = _evidence_as_of(source)
    fresh, evidence_age_hours = _is_fresh(evidence_as_of, now)

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
        reasons.append("Current reviewed monthly-equivalent income evidence is unavailable.")
    elif observed < INCOME_TARGET_MONTHLY_PERCENT:
        reasons.append(f"Observed monthly-equivalent income {observed:.4g}% is below the {INCOME_TARGET_MONTHLY_PERCENT:.4g}% minimum.")
    if age_months is not None:
        if age_months < MINIMUM_MECHANISM_AGE_MONTHS:
            reasons.append(f"Income mechanism age {age_months:.4g} months is below the {MINIMUM_MECHANISM_AGE_MONTHS:.4g}-month minimum.")
    elif maturity_status not in {"MATURE", "QUALIFIED", "PASS"}:
        reasons.append("Reviewed two-month mechanism maturity evidence is unavailable.")
    if vehicle_status in {"DELISTED", "LIQUIDATED", "TERMINATED", "INACTIVE", "CLOSED"}:
        reasons.append(f"Income vehicle status is {vehicle_status}.")
    elif vehicle_status not in {"ACTIVE", "TRADABLE"}:
        reasons.append("Current reviewed vehicle-active evidence is unavailable.")
    if mapping_status in {"DISQUALIFIED", "REJECTED", "INVALID", "RESEARCH_REQUIRED"}:
        reasons.append(f"Income mapping status is {mapping_status}.")
    if not fresh:
        if evidence_age_hours is None:
            reasons.append("Income mapping evidence timestamp is unavailable or invalid.")
        else:
            reasons.append(f"Income mapping evidence is stale ({evidence_age_hours:.1f}h old; maximum {MAPPING_EVIDENCE_MAX_AGE_HOURS:.1f}h).")

    qualified = not reasons
    status = "QUALIFIED" if qualified else "DISQUALIFIED"
    # Missing/unreviewed evidence is research rather than a factual negative.
    if reasons and not source:
        status = "RESEARCH_REQUIRED"
    elif reasons and any("unavailable" in reason.lower() for reason in reasons):
        status = "RESEARCH_REQUIRED"

    return {
        "underlying_symbol": symbol.upper(),
        "income_symbol": income_symbol,
        "income_mechanism": mechanism,
        "distribution_frequency": frequency or None,
        "income_target_monthly_percent": INCOME_TARGET_MONTHLY_PERCENT,
        "observed_income_monthly_percent": observed,
        "mechanism_age_months": age_months,
        "minimum_mechanism_age_months": MINIMUM_MECHANISM_AGE_MONTHS,
        "vehicle_status": vehicle_status or None,
        "mapping_status": mapping_status or None,
        "evidence_as_of": evidence_as_of,
        "freshness_status": "FRESH" if fresh else "STALE_OR_UNAVAILABLE",
        "evidence_max_age_hours": MAPPING_EVIDENCE_MAX_AGE_HOURS,
        "eligibility_status": status,
        "watchlist_admission_allowed": qualified,
        "manual_review_required": True,
        "automatic_activation_allowed": False,
        "reasons": reasons,
        "policy": "DIVIDEND_GATEWAY_CONTINUOUS_REFRESH_FAIL_CLOSED",
    }


def apply_dividend_gateway_to_watchlist(
    row: Mapping[str, Any], root: str | Path = ".", *, now: datetime | None = None
) -> dict[str, Any]:
    """Admit only currently qualified mappings to the Dividend Watchlist.

    Existing held paper positions are retained in the row for lifecycle review;
    gateway failure never auto-sells a position.  Non-held unqualified candidates
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
    result["dividend_gateway_policy"] = "DIVIDEND_GATEWAY_CONTINUOUS_REFRESH_FAIL_CLOSED"
    return result
