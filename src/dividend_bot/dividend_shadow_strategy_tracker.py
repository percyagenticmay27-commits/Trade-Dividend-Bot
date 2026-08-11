"""Daily paper-only shadow benchmark for pair timing strategies."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Mapping

PAPER_TRADE_MODE = True
SHADOW_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

LEGACY_STARTING_VALUE = 100.0
A_WEIGHT = 0.70
B_WEIGHT = 0.30
STRATEGIES = ("STRATEGY_A", "STRATEGY_B")
DEFAULT_STATE_PATH = Path("state/dividend_strategy_shadow_state.json")
DEFAULT_REPORT_PATH = Path("results/dividend_strategy_shadow_performance.json")


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(value)


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _entry_rows(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = report.get("entries")
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("symbol") or "").strip().upper(): row
        for row in rows
        if isinstance(row, Mapping) and str(row.get("symbol") or "").strip()
    }


def _signals_for_pair(
    pair: str,
    config: Mapping[str, Any],
    entry_rows: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    candidates = (
        str(config.get("a_signal") or "").upper(),
        str(config.get("b_signal") or "").upper(),
        str(config.get("a") or "").upper(),
        str(config.get("b") or "").upper(),
    )
    for symbol in candidates:
        row = entry_rows.get(symbol)
        signals = row.get("strategy_signals") if isinstance(row, Mapping) else None
        if isinstance(signals, Mapping):
            return signals
    return {}


def _new_strategy_state(as_of: str) -> dict[str, Any]:
    return {
        "evaluation_start": as_of,
        "evaluation_end": as_of,
        "starting_value": STARTING_VALUE,
        "cash": STARTING_VALUE,
        "a_shares": 0.0,
        "b_shares": 0.0,
        "in_market": False,
        "current_value": STARTING_VALUE,
        "peak_value": STARTING_VALUE,
        "max_drawdown_percent": 0.0,
        "observation_count": 0,
        "completed_trade_count": 0,
        "last_observation_date": None,
        "last_action": "SHADOW_INITIALIZED",
    }


def _allocation_basis(actual: Mapping[str, Any]) -> float:
    """Return the authoritative paper-capital bucket assigned to this pair."""
    try:
        basis = float(actual["capital_bucket"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("pair paper state has no valid capital_bucket") from exc
    if basis <= 0:
        raise ValueError("pair capital_bucket must be positive")
    return basis


def _rebase_strategy_state(row: dict[str, Any], allocation_basis: float) -> dict[str, Any]:
    """Scale legacy or reallocated virtual money without changing performance."""
    try:
        prior_basis = float(row.get("starting_value") or LEGACY_STARTING_VALUE)
    except (TypeError, ValueError):
        prior_basis = LEGACY_STARTING_VALUE
    if prior_basis <= 0:
        prior_basis = LEGACY_STARTING_VALUE
    factor = allocation_basis / prior_basis
    if abs(factor - 1.0) > 1e-12:
        for field in ("cash", "a_shares", "b_shares", "current_value", "peak_value"):
            try:
                row[field] = float(row.get(field, 0.0)) * factor
            except (TypeError, ValueError):
                row[field] = 0.0
    row["starting_value"] = allocation_basis
    row["allocation_basis"] = allocation_basis
    return row


def _strategy_signal(signals: Mapping[str, Any], strategy_id: str) -> tuple[bool, bool]:
    if strategy_id == "STRATEGY_A":
        row = signals.get("strategy_a") if isinstance(signals.get("strategy_a"), Mapping) else {}
        return bool(row.get("buy_trigger")), bool(row.get("sell_trigger"))
    row = signals.get("strategy_b") if isinstance(signals.get("strategy_b"), Mapping) else {}
    return bool(row.get("buy_eligible")), bool(row.get("sell_trigger"))


def _value(row: Mapping[str, Any], a_price: float, b_price: float) -> float:
    if bool(row.get("in_market")):
        return float(row.get("a_shares", 0)) * a_price + float(row.get("b_shares", 0)) * b_price
    return float(row.get("cash", STARTING_VALUE))


def update_shadow_strategy_performance(
    *,
    paper_state: Mapping[str, Any],
    entry_score_report: Mapping[str, Any],
    pair_config: Mapping[str, Mapping[str, Any]],
    state_path: str | Path = DEFAULT_STATE_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    as_of = str(paper_state.get("as_of_date") or paper_state.get("last_processed_date") or "")
    if not as_of:
        raise ValueError("paper state has no as-of date")
    date.fromisoformat(as_of[:10])
    shadow_file = Path(state_path)
    stored = _read_mapping(shadow_file)
    pairs_state = stored.get("pairs") if isinstance(stored.get("pairs"), Mapping) else {}
    pairs_state = {str(pair): dict(value) for pair, value in pairs_state.items() if isinstance(value, Mapping)}
    entries = _entry_rows(entry_score_report)

    performance: list[dict[str, Any]] = []
    for pair, config in pair_config.items():
        actual = paper_state.get("pairs", {}).get(pair)
        if not isinstance(actual, Mapping):
            continue
        prices = actual.get("last_prices") if isinstance(actual.get("last_prices"), Mapping) else {}
        try:
            a_price = float(prices["A"])
            b_price = float(prices["B"])
        except (KeyError, TypeError, ValueError):
            continue
        if a_price <= 0 or b_price <= 0:
            continue
        try:
            allocation_basis = _allocation_basis(actual)
        except ValueError:
            continue
        signals = _signals_for_pair(pair, config, entries)
        pair_shadow = pairs_state.setdefault(pair, {})
        for strategy_id in STRATEGIES:
            row = pair_shadow.get(strategy_id)
            row = (
                _rebase_strategy_state(dict(row), allocation_basis)
                if isinstance(row, Mapping)
                else _new_strategy_state(as_of, allocation_basis)
            )
            duplicate_date = row.get("last_observation_date") == as_of
            buy, sell = _strategy_signal(signals, strategy_id)
            current_before = _value(row, a_price, b_price)
            action = "SHADOW_HOLD"
            if not duplicate_date and not row.get("in_market") and buy:
                row["cash"] = 0.0
                row["a_shares"] = current_before * A_WEIGHT / a_price
                row["b_shares"] = current_before * B_WEIGHT / b_price
                row["in_market"] = True
                action = "SHADOW_BUY"
            elif not duplicate_date and row.get("in_market") and sell:
                row["cash"] = current_before
                row["a_shares"] = 0.0
                row["b_shares"] = 0.0
                row["in_market"] = False
                row["completed_trade_count"] = int(row.get("completed_trade_count", 0)) + 1
                action = "SHADOW_SELL"
            elif duplicate_date:
                action = str(row.get("last_action") or "SHADOW_HOLD")

            current = _value(row, a_price, b_price)
            peak = max(float(row.get("peak_value", STARTING_VALUE)), current)
            drawdown = ((peak - current) / peak * 100.0) if peak > 0 else 0.0
            row.update(
                {
                    "evaluation_end": as_of,
                    "current_value": round(current, 8),
                    "peak_value": round(peak, 8),
                    "max_drawdown_percent": round(
                        max(float(row.get("max_drawdown_percent", 0.0)), drawdown),
                        8,
                    ),
                    "last_observation_date": as_of,
                    "last_action": action,
                }
            )
            if not duplicate_date:
                row["observation_count"] = int(row.get("observation_count", 0)) + 1
            pair_shadow[strategy_id] = row
            performance.append(
                {
                    "pair": pair,
                    "strategy_id": strategy_id,
                    "role": "STRATEGY_A_BASELINE" if strategy_id == "STRATEGY_A" else "TEST_CANDIDATE",
                    "evaluation_start": row["evaluation_start"],
                    "evaluation_end": as_of,
                    "total_return_percent": round((current / STARTING_VALUE - 1.0) * 100.0, 8),
                    "max_drawdown_percent": round(float(row["max_drawdown_percent"]), 8),
                    "observation_count": int(row["observation_count"]),
                    "completed_trade_count": int(row["completed_trade_count"]),
                    "current_shadow_value": round(current, 8),
                    "virtual_gain_loss": round(current - allocation_basis, 8),
                    "in_market": bool(row["in_market"]),
                    "last_action": action,
                    "paper_trade_mode": True,
                    "shadow_only": True,
                    "broker_execution_enabled": False,
                    "capital_movement_enabled": False,
                }
            )

    state_payload = {
        "schema_version": "1.0",
        "as_of_date": as_of,
        "starting_value_per_strategy_pair": STARTING_VALUE,
        "paper_trade_mode": True,
        "shadow_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "pairs": pairs_state,
    }
    report = {
        "schema_version": "1.1",
        "as_of_date": as_of,
        "methodology": "ISOLATED_PAIR_ALLOCATION_EQUIVALENT_BENCHMARK_70_30_SLEEVES",
        "capital_basis_policy": "MATCH_AUTHORITATIVE_PAIR_CAPITAL_BUCKET",
        "performance": performance,
        "paper_trade_mode": True,
        "shadow_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }
    _write(shadow_file, state_payload)
    _write(Path(report_path), report)
    return report
