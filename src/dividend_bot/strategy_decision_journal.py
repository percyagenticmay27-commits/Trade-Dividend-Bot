"""Strategy-scoped, paper-only Decision Journal contract.

The Enterprise host may render journals for many registered strategies, but each
strategy KPI workspace must receive only the selected strategy's own decisions.
Dividend decisions are ecosystem-selection decisions; Swing decisions are
individual-opportunity decisions.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .enterprise_strategy_decision_canonicalizer import (
    canonicalize_strategy_decision_event,
)

MODULE_NAME = "strategy_decision_journal"
MODULE_VERSION = "1.0.2"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
READ_ONLY = True

SUPPORTED_STRATEGY_KINDS = {"DIVIDEND", "SWING"}
SUPPORTED_DIVIDEND_MODES = {"PAIR", "SELF_FUNDED"}


class DecisionJournalError(ValueError):
    """Raised when supplied decision evidence violates the journal contract."""


def _nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DecisionJournalError(f"{field} is required")
    return text


def _first_nonempty(entry: Mapping[str, Any], *fields: str) -> Any:
    for field in fields:
        value = entry.get(field)
        if str(value or "").strip():
            return value
    return None


def _timestamp(value: Any) -> str:
    text = _nonempty(value, "decision_timestamp")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionJournalError("decision_timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DecisionJournalError(f"{field} must be a list")
    return [_nonempty(item, field) for item in value]


def _mapping_list(value: Any, field: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DecisionJournalError(f"{field} must be a list")
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise DecisionJournalError(f"{field} entries must be objects")
        rows.append(deepcopy(dict(item)))
    return rows


def _normalize_images(entry: Mapping[str, Any]) -> list[dict[str, str]]:
    images = entry.get("images", [])
    if not isinstance(images, list):
        raise DecisionJournalError("images must be a list")
    normalized: list[dict[str, str]] = []
    for image in images:
        if not isinstance(image, Mapping):
            raise DecisionJournalError("image entries must be objects")
        normalized.append(
            {
                "path": _nonempty(image.get("path"), "images.path"),
                "caption": _nonempty(image.get("caption"), "images.caption"),
                "image_type": str(image.get("image_type") or "EVIDENCE").strip().upper(),
            }
        )
    return normalized


def _normalize_common(entry: Mapping[str, Any], strategy_id: str, kind: str) -> dict[str, Any]:
    actual_strategy_id = _nonempty(entry.get("strategy_id"), "strategy_id")
    if actual_strategy_id != strategy_id:
        raise DecisionJournalError(
            f"Cross-strategy decision rejected: expected {strategy_id}, got {actual_strategy_id}"
        )

    entry_kind = str(entry.get("strategy_kind") or kind).strip().upper()
    if entry_kind != kind:
        raise DecisionJournalError(
            f"strategy_kind mismatch: expected {kind}, got {entry_kind}"
        )

    return {
        "decision_id": _nonempty(entry.get("decision_id"), "decision_id"),
        "decision_timestamp": _timestamp(entry.get("decision_timestamp")),
        "strategy_id": strategy_id,
        "strategy_kind": kind,
        "decision_type": _nonempty(entry.get("decision_type"), "decision_type").upper(),
        "status": _nonempty(entry.get("status"), "status").upper(),
        "summary": _nonempty(entry.get("summary"), "summary"),
        "final_rationale": _nonempty(entry.get("final_rationale"), "final_rationale"),
        "committee_evidence": _mapping_list(entry.get("committee_evidence"), "committee_evidence"),
        "images": _normalize_images(entry),
        "lifecycle_event_id": str(entry.get("lifecycle_event_id") or "").strip() or None,
    }


def _normalize_dividend(entry: Mapping[str, Any], common: dict[str, Any]) -> dict[str, Any]:
    mode_value = _first_nonempty(entry, "ecosystem_mode", "ecosystem_node") or "PAIR"
    mode = str(mode_value).strip().upper()
    if mode not in SUPPORTED_DIVIDEND_MODES:
        raise DecisionJournalError(f"Unsupported dividend ecosystem_mode: {mode}")

    ecosystem_value = _first_nonempty(entry, "ecosystem_id", "ecosystem")
    ecosystem_name_value = _first_nonempty(
        entry, "ecosystem_name", "ecosystem", "ecosystem_id"
    )
    ecosystem = {
        "ecosystem_id": _nonempty(ecosystem_value, "ecosystem_id"),
        "ecosystem_name": _nonempty(ecosystem_name_value, "ecosystem_name"),
        "mode": mode,
    }

    if mode == "PAIR":
        ecosystem["income_leg"] = _nonempty(entry.get("income_leg"), "income_leg")
        ecosystem["leverage_leg"] = _nonempty(entry.get("leverage_leg"), "leverage_leg")
        ecosystem["income_alternatives"] = _string_list(
            entry.get("income_alternatives"), "income_alternatives"
        )
        ecosystem["leverage_alternatives"] = _string_list(
            entry.get("leverage_alternatives"), "leverage_alternatives"
        )
        ecosystem["income_leg_reason"] = _nonempty(
            entry.get("income_leg_reason"), "income_leg_reason"
        )
        ecosystem["leverage_leg_reason"] = _nonempty(
            entry.get("leverage_leg_reason"), "leverage_leg_reason"
        )
        ecosystem["pair_compatibility_reason"] = _nonempty(
            entry.get("pair_compatibility_reason"), "pair_compatibility_reason"
        )
    else:
        ecosystem["primary_instrument"] = _nonempty(
            entry.get("primary_instrument"), "primary_instrument"
        )
        ecosystem["self_funding_reason"] = _nonempty(
            entry.get("self_funding_reason"), "self_funding_reason"
        )
        ecosystem["alternatives"] = _string_list(entry.get("alternatives"), "alternatives")

    underlying_context = entry.get("underlying_context")
    if underlying_context is not None and not isinstance(underlying_context, Mapping):
        raise DecisionJournalError("underlying_context must be an object when supplied")

    normalized = dict(common)
    normalized.update(
        {
            "decision_object_type": "DIVIDEND_ECOSYSTEM",
            "ecosystem": ecosystem,
            "underlying_context": deepcopy(dict(underlying_context or {})),
            "selection_comparison": _mapping_list(
                entry.get("selection_comparison"), "selection_comparison"
            ),
        }
    )
    return normalized


def _normalize_swing(entry: Mapping[str, Any], common: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(common)
    normalized.update(
        {
            "decision_object_type": "SWING_OPPORTUNITY",
            "symbol": _nonempty(entry.get("symbol"), "symbol"),
            "committee_rank": entry.get("committee_rank"),
            "opportunity_quality": entry.get("opportunity_quality"),
            "entry_score": entry.get("entry_score"),
            "strategy_assignment": str(entry.get("strategy_assignment") or "").strip() or None,
            "alternatives": _mapping_list(entry.get("alternatives"), "alternatives"),
        }
    )
    return normalized


def normalize_decision(
    entry: Mapping[str, Any], *, strategy_id: str, strategy_kind: str
) -> dict[str, Any]:
    """Validate and normalize one strategy-owned decision entry."""

    if not isinstance(entry, Mapping):
        raise DecisionJournalError("decision entry must be an object")
    strategy_id = _nonempty(strategy_id, "strategy_id")
    kind = _nonempty(strategy_kind, "strategy_kind").upper()
    if kind not in SUPPORTED_STRATEGY_KINDS:
        raise DecisionJournalError(f"Unsupported strategy_kind: {kind}")

    canonical_entry = canonicalize_strategy_decision_event(entry)
    common = _normalize_common(canonical_entry, strategy_id, kind)
    if kind == "DIVIDEND":
        return _normalize_dividend(canonical_entry, common)
    return _normalize_swing(canonical_entry, common)


def build_strategy_decision_journal(
    *,
    strategy_id: str,
    strategy_kind: str,
    strategy_name: str,
    decisions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one newest-first Decision Journal for one strategy KPI workspace."""

    strategy_id = _nonempty(strategy_id, "strategy_id")
    strategy_name = _nonempty(strategy_name, "strategy_name")
    kind = _nonempty(strategy_kind, "strategy_kind").upper()

    normalized = [
        normalize_decision(entry, strategy_id=strategy_id, strategy_kind=kind)
        for entry in decisions
    ]
    normalized.sort(key=lambda item: item["decision_timestamp"], reverse=True)

    return {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "strategy_kind": kind,
        "journal_scope": "SELECTED_STRATEGY_ONLY",
        "sort_order": "NEWEST_FIRST",
        "decision_count": len(normalized),
        "decisions": normalized,
        "paper_trade_mode": PAPER_TRADE_MODE,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "broker_execution_enabled": BROKER_EXECUTION_ENABLED,
        "read_only": READ_ONLY,
    }
