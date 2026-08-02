"""Read-only adapter between strategy Decision Journals and Enterprise KPI tabs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .strategy_decision_journal_renderer import render_strategy_decision_journal

MODULE_NAME = "enterprise_decision_journal_adapter"
MODULE_VERSION = "1.0.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
READ_ONLY = True

JOURNAL_FILES = {
    "DIVIDEND-001": "dividend_strategy_decision_journal.json",
    "SWING-001": "swing_strategy_decision_journal.json",
}


class EnterpriseDecisionJournalAdapterError(ValueError):
    """Raised when a selected strategy journal violates Enterprise isolation."""


def _empty_journal(strategy_id: str, strategy_name: str) -> dict[str, Any]:
    strategy_kind = "DIVIDEND" if strategy_id == "DIVIDEND-001" else "SWING"
    return {
        "schema_version": "1.0",
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "strategy_kind": strategy_kind,
        "strategy_type": strategy_kind,
        "journal_scope": "SELECTED_STRATEGY_ONLY",
        "sort_order": "NEWEST_FIRST",
        "decision_count": 0,
        "decisions": [],
        "evidence_status": "NOT_REPORTED",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only": True,
    }


def load_selected_strategy_journal(
    *,
    results_dir: str | Path,
    strategy_id: str,
    strategy_name: str,
) -> tuple[dict[str, Any], list[str]]:
    """Load only the selected strategy journal and return safe UI warnings."""
    strategy_id = str(strategy_id or "").strip()
    if strategy_id not in JOURNAL_FILES:
        raise EnterpriseDecisionJournalAdapterError(
            f"Unsupported selected strategy_id: {strategy_id or 'missing'}"
        )

    path = Path(results_dir) / JOURNAL_FILES[strategy_id]
    if not path.is_file():
        return _empty_journal(strategy_id, strategy_name), [
            f"Decision Journal artifact is not available for {strategy_id}: {path}"
        ]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _empty_journal(strategy_id, strategy_name), [
            f"Decision Journal artifact could not be read for {strategy_id}: {exc}"
        ]
    if not isinstance(payload, Mapping):
        raise EnterpriseDecisionJournalAdapterError("Decision Journal must be a JSON object")

    actual_strategy_id = str(payload.get("strategy_id") or "").strip()
    if actual_strategy_id != strategy_id:
        raise EnterpriseDecisionJournalAdapterError(
            f"Cross-strategy journal rejected: selected {strategy_id}, artifact {actual_strategy_id or 'missing'}"
        )
    if str(payload.get("journal_scope") or "") != "SELECTED_STRATEGY_ONLY":
        raise EnterpriseDecisionJournalAdapterError(
            "Decision Journal must declare SELECTED_STRATEGY_ONLY scope"
        )

    journal = dict(payload)
    journal.setdefault("strategy_name", strategy_name)
    journal.setdefault("strategy_type", journal.get("strategy_kind"))
    return journal, []


def build_decision_journal_tab(
    *,
    results_dir: str | Path,
    strategy_id: str,
    strategy_name: str,
) -> dict[str, Any]:
    """Build the selected KPI Decision Journal tab payload and HTML fragment."""
    journal, warnings = load_selected_strategy_journal(
        results_dir=results_dir,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
    )
    return {
        "tab_id": "decision-journal",
        "tab_label": "Decision Journal",
        "strategy_id": strategy_id,
        "decision_count": int(journal.get("decision_count") or 0),
        "evidence_status": str(journal.get("evidence_status") or "NOT_REPORTED"),
        "sort_order": "NEWEST_FIRST",
        "html": render_strategy_decision_journal(journal),
        "warnings": warnings,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only": True,
    }
