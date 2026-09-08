"""Strict read-only bridge from Enterprise Market Data to authenticated Codex MCP."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ALLOWED_OPERATIONS = {"get_quote", "get_history"}
FORBIDDEN_TERMS = {"order", "buy", "sell", "cancel", "transfer", "position", "execute"}
FORBIDDEN_OUTPUT_KEYS = {"token", "oauth", "authorization", "cookie", "secret", "account_number"}


def _validate_operation(operation: str) -> None:
    if operation not in ALLOWED_OPERATIONS:
        raise ValueError("unsupported market-data operation")
    if any(term in operation.lower() for term in FORBIDDEN_TERMS):
        raise ValueError("order-related operation rejected")


def _sanitize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("codex output must be one JSON object")
    lowered_keys = {str(key).lower() for key in payload}
    if FORBIDDEN_OUTPUT_KEYS.intersection(lowered_keys):
        raise RuntimeError("sensitive authentication/account data rejected")
    payload = dict(payload)
    payload["provider"] = "ROBINHOOD_MCP"
    return payload


def run_codex_market_data(
    operation: str,
    symbol: str,
    period: str = "",
    interval: str = "",
    *,
    timeout_seconds: int = 45,
    codex_path: str = "/usr/local/bin/codex",
) -> dict[str, Any]:
    """Invoke root's authenticated Codex profile for one read-only operation.

    Production deployment calls this only from the root-owned handoff entry point.
    The unprivileged AI CIO runtime reads the resulting sanitized JSON instead of
    accessing root's Codex profile or OAuth material.
    """
    _validate_operation(operation)
    prompt = (
        "Use only the enabled robinhood-trading MCP connection for read-only market data. "
        "Never place, preview, cancel, or modify orders; never access transfers or account controls. "
        f"Operation={operation}; symbol={symbol}; period={period or 'n/a'}; interval={interval or 'n/a'}. "
        "Return exactly one JSON object and no markdown. For get_quote include symbol, price, "
        "quote_timestamp, trading_date, source_type, confidence, warnings. For get_history include "
        "symbol, interval, period, generated_at, corporate_action_adjusted, split_history, "
        "dividend_history, warnings, and bars with date/open/high/low/close/adjusted_close/volume."
    )
    completed = subprocess.run(
        [codex_path, "exec", "--skip-git-repo-check", prompt],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/root"},
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"codex exec failed with exit code {completed.returncode}: {completed.stderr[-500:]}"
        )
    text = completed.stdout.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("codex output did not contain JSON")
    return _sanitize_payload(json.loads(text[start : end + 1]))


def read_codex_market_data_handoff(
    operation: str,
    symbol: str,
    period: str = "",
    interval: str = "",
    *,
    handoff_dir: str | Path = "/run/enterprise-market-data-handoff",
) -> dict[str, Any]:
    """Read a sanitized root-produced handoff without accessing credentials."""
    _validate_operation(operation)
    safe_symbol = symbol.strip().upper()
    if not safe_symbol or not all(character.isalnum() or character in ".-" for character in safe_symbol):
        raise ValueError("invalid symbol")
    suffix = "quote" if operation == "get_quote" else "history"
    path = Path(handoff_dir) / f"{safe_symbol}.{suffix}.json"
    if not path.is_file():
        raise RuntimeError(f"Robinhood MCP handoff unavailable: {path}")
    payload = _sanitize_payload(json.loads(path.read_text(encoding="utf-8")))
    if str(payload.get("symbol", "")).upper() != safe_symbol:
        raise RuntimeError("handoff symbol does not match request")
    if operation == "get_history":
        if period and str(payload.get("period", period)) != period:
            raise RuntimeError("handoff period does not match request")
        if interval and str(payload.get("interval", interval)) != interval:
            raise RuntimeError("handoff interval does not match request")
    return payload
