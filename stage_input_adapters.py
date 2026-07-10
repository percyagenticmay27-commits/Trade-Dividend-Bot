"""Deterministic adapters between Dividend Bot stage report schemas.

The adapters convert already-built upstream reports and the shared read-only market
snapshot into keyword arguments that an existing downstream builder can accept.
They never access providers or mutate portfolio state.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Iterable, Mapping


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(payload: Mapping[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(key, [])
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _index_by_symbol(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        symbol = row.get("symbol") or row.get("income_symbol") or row.get("growth_symbol")
        if isinstance(symbol, str) and symbol.strip():
            result[symbol.strip().upper()] = row
    return result


def build_portfolio_decision_candidates(stage_payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    pairing = _mapping(stage_payloads.get("opportunity_pairing"))
    ranking = _mapping(stage_payloads.get("dividend_ranking"))
    conviction = _mapping(stage_payloads.get("conviction"))
    entry = _mapping(stage_payloads.get("entry_score"))
    momentum = _mapping(stage_payloads.get("momentum_score"))

    ranking_index = _index_by_symbol(_rows(ranking, "rankings", "entries"))
    candidates = _rows(pairing, "opportunities", "ranked_opportunities")
    if not candidates:
        candidates = _rows(ranking, "rankings", "entries")

    conviction_score = conviction.get("conviction_score", 0)
    entry_score = entry.get("entry_score", 0)
    momentum_score = momentum.get("momentum_score", 0)
    result: list[dict[str, Any]] = []
    for raw in candidates:
        row = dict(raw)
        symbol = row.get("symbol") or row.get("income_symbol") or row.get("growth_symbol") or "UNKNOWN"
        symbol = str(symbol).upper()
        ranked = ranking_index.get(symbol, {})
        result.append({
            **row,
            "symbol": symbol,
            "opportunity_score": row.get("combined_score", row.get("opportunity_score", 0)),
            "conviction_score": row.get("conviction_score", conviction_score),
            "entry_score": row.get("entry_score", entry_score),
            "momentum_score": row.get("momentum_score", momentum_score),
            "dividend_ranking_score": ranked.get("overall_score", row.get("overall_score", 0)),
            "self_funding_score": row.get("self_funding_score", 0),
            "confidence": row.get("confidence", conviction.get("confidence", 0.0)),
            "confidence_level": row.get("confidence_level", conviction.get("confidence_level", "LOW")),
        })
    return result


def build_lifecycle_holdings(stage_payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    construction = _mapping(stage_payloads.get("portfolio_construction"))
    allocation = _mapping(stage_payloads.get("capital_allocation"))
    decisions = _mapping(stage_payloads.get("portfolio_decision"))
    rows = _rows(construction, "positions", "holdings", "portfolio_positions")
    if not rows:
        rows = _rows(allocation, "allocations", "capital_allocations")
    if not rows:
        rows = _rows(decisions, "portfolio_decisions")
    return rows


def _candidate_kwargs(stage_name: str, stage_payloads: Mapping[str, Mapping[str, Any]], root_path: str) -> Dict[str, Any]:
    p = stage_payloads
    decisions = _mapping(p.get("portfolio_decision"))
    allocation = _mapping(p.get("capital_allocation"))
    construction = _mapping(p.get("portfolio_construction"))
    lifecycle = _mapping(p.get("portfolio_lifecycle"))
    daily = _mapping(p.get("daily_command_center"))
    market_data = _mapping(p.get("market_data"))
    market_records = _rows(market_data, "records")

    mapping: Dict[str, Dict[str, Any]] = {
        "portfolio_decision": {
            "decisions": build_portfolio_decision_candidates(p),
            "root_path": root_path,
        },
        "capital_allocation": {
            "candidates": _rows(decisions, "portfolio_decisions"),
            "decisions": _rows(decisions, "portfolio_decisions"),
            "portfolio_value": 500.0,
            "account_value": 500.0,
        },
        "portfolio_construction": {
            "allocations": _rows(allocation, "allocations", "capital_allocations"),
            "candidates": _rows(allocation, "allocations", "capital_allocations"),
            "portfolio_value": allocation.get("portfolio_value", allocation.get("account_value", 500.0)),
        },
        "portfolio_rebalance": {
            "holdings": build_lifecycle_holdings(p),
            "watchlist": _rows(_mapping(p.get("opportunity_pairing")), "opportunities", "ranked_opportunities"),
            "market_regime": _mapping(p.get("market_regime")).get("market_regime", "UNKNOWN"),
        },
        "income_reinvestment": {
            "distributions": [],
            "portfolio_value": lifecycle.get("portfolio_value", construction.get("portfolio_value", 500.0)),
            "cash_balance": lifecycle.get("cash_balance", allocation.get("cash_balance", 0.0)),
            "market_regime": _mapping(p.get("market_regime")).get("market_regime", "UNKNOWN"),
            "opportunities": _rows(_mapping(p.get("opportunity_pairing")), "opportunities", "ranked_opportunities"),
        },
        "portfolio_lifecycle": {
            "holdings": build_lifecycle_holdings(p),
            "portfolio_value": construction.get("portfolio_value", allocation.get("portfolio_value", 500.0)),
            "cash_balance": allocation.get("cash_balance", allocation.get("available_cash", 0.0)),
            "market_regime": _mapping(p.get("market_regime")).get("market_regime", "UNKNOWN"),
        },
        "daily_command_center": {
            "portfolio_lifecycle": _mapping(p.get("portfolio_lifecycle")),
            "income_reinvestment": _mapping(p.get("income_reinvestment")),
            "portfolio_rebalance": _mapping(p.get("portfolio_rebalance")),
            "portfolio_construction": construction,
            "capital_allocation": allocation,
            "portfolio_decision": decisions,
            "conviction": _mapping(p.get("conviction")),
            "entry_score": _mapping(p.get("entry_score")),
            "opportunity_pairing": _mapping(p.get("opportunity_pairing")),
            "dividend_ranking": _mapping(p.get("dividend_ranking")),
        },
        "weekly_portfolio_review": {
            "daily_reports": [daily] if daily else [],
            "daily_command_centers": [daily] if daily else [],
            "daily_command_center": daily,
        },
        "strategy_performance_analytics": {
            "trades": [],
        },
        "monthly_portfolio_review": {
            "daily_reports": [daily] if daily else [],
            "daily_command_centers": [daily] if daily else [],
            "daily_command_center": daily,
            "starting_portfolio_value": daily.get("portfolio_value", 0.0),
        },
    }
    candidates = dict(mapping.get(stage_name, {}))
    candidates.update({
        "market_data_snapshot": market_data,
        "market_data": market_data,
        "market_records": market_records,
        "quotes": market_records,
    })
    return candidates


def prepare_stage_kwargs(
    stage_name: str,
    stage_payloads: Mapping[str, Mapping[str, Any]],
    builder: Callable[..., Any],
    root_path: str = ".",
) -> Dict[str, Any]:
    """Return only adapter arguments accepted by the target builder signature."""
    candidates = _candidate_kwargs(stage_name, stage_payloads, root_path)
    signature = inspect.signature(builder)
    accepts_var_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if accepts_var_kwargs:
        return candidates
    return {name: value for name, value in candidates.items() if name in signature.parameters}
