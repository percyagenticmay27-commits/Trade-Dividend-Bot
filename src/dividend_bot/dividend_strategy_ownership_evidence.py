"""Read-only normalization of persisted Dividend strategy ownership for Enterprise evidence."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

VALID_OWNERS = {"STRATEGY_A", "STRATEGY_B", "LEGACY_UNASSIGNED"}


def _owner(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text if text in VALID_OWNERS else None


def _pair_symbols(pair: str) -> tuple[str | None, str | None]:
    parts = [item.strip().upper() for item in str(pair or "").split("/") if item.strip()]
    return (parts[0] if parts else None, parts[1] if len(parts) > 1 else None)


def build_strategy_ownership_index(state: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Return current and latest-exit ownership evidence keyed by symbol.

    LEGACY_UNASSIGNED is retained as an explicit lifecycle-management status. It
    does not mean Strategy A or Strategy B was reconstructed retroactively.
    """
    result: dict[str, dict[str, Any]] = {}
    pairs = state.get("pairs") if isinstance(state, Mapping) else None
    if not isinstance(pairs, Mapping):
        return result

    for pair_name, raw in pairs.items():
        if not isinstance(raw, Mapping):
            continue
        symbol_a, symbol_b = _pair_symbols(str(pair_name))
        pair_owner = _owner(raw.get("strategy_owner"))
        pair_source = raw.get("strategy_ownership_source")
        pair_last_owner = _owner(raw.get("last_exit_strategy_owner"))
        pair_last_reasons = list(raw.get("last_exit_strategy_reasons") or []) if isinstance(raw.get("last_exit_strategy_reasons"), list) else []

        for side, symbol in (("A", symbol_a), ("B", symbol_b)):
            if not symbol:
                continue
            key = side.lower()
            current_owner = _owner(raw.get(f"{key}_strategy_owner")) or pair_owner
            source = raw.get(f"{key}_strategy_ownership_source") or pair_source
            last_owner = _owner(raw.get(f"{key}_last_exit_strategy_owner")) or pair_last_owner
            last_reasons = raw.get(f"{key}_last_exit_strategy_reasons")
            if isinstance(last_reasons, list):
                normalized_reasons = [str(item) for item in last_reasons if str(item).strip()]
            else:
                normalized_reasons = [str(item) for item in pair_last_reasons if str(item).strip()]

            result[symbol] = {
                "strategy_owner": current_owner,
                "entry_method": current_owner,
                "strategy_ownership_source": str(source) if source not in (None, "") else None,
                "last_exit_strategy_owner": last_owner,
                "exit_method": last_owner,
                "last_exit_strategy_reasons": normalized_reasons,
                "last_exit_reason": ", ".join(normalized_reasons) if normalized_reasons else None,
                "pair": str(pair_name),
                "sleeve": side,
                "evidence_source": "paper_state.json",
            }
    return result


def enrich_holdings_with_strategy_ownership(
    holdings: Iterable[Mapping[str, Any]],
    state: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    index = build_strategy_ownership_index(state)
    enriched: list[dict[str, Any]] = []
    for raw in holdings:
        row = dict(raw)
        symbol = str(row.get("symbol") or "").strip().upper()
        detail = index.get(symbol)
        if detail:
            for key in ("strategy_owner", "entry_method", "strategy_ownership_source"):
                row[key] = detail.get(key)
        enriched.append(row)
    return enriched


def enrich_lifecycle_with_strategy_ownership(
    lifecycle: Iterable[Mapping[str, Any]],
    state: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    index = build_strategy_ownership_index(state)
    enriched: list[dict[str, Any]] = []
    for raw in lifecycle:
        row = dict(raw)
        symbol = str(row.get("symbol") or "").strip().upper()
        detail = index.get(symbol)
        if detail:
            if bool(row.get("is_current_holding")):
                row["strategy_owner"] = detail.get("strategy_owner")
                row["entry_method"] = detail.get("entry_method")
                row["strategy_ownership_source"] = detail.get("strategy_ownership_source")
            if str(row.get("lifecycle_status") or "").upper() not in {"OPEN", "REENTERED", "RESERVE", "NEVER_ENTERED"}:
                row["entry_method"] = detail.get("last_exit_strategy_owner")
                row["last_exit_strategy_owner"] = detail.get("last_exit_strategy_owner")
                row["exit_method"] = detail.get("exit_method")
                row["last_exit_strategy_reasons"] = detail.get("last_exit_strategy_reasons") or []
                row["last_exit_reason"] = detail.get("last_exit_reason")
                row["strategy_exit_evidence_source"] = detail.get("evidence_source")
        enriched.append(row)
    return enriched
