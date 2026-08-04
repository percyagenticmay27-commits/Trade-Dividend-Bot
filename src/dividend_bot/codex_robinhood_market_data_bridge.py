"""Strict read-only bridge from Enterprise Market Data to authenticated Codex MCP."""
from __future__ import annotations
import json
import subprocess
from typing import Any

ALLOWED_OPERATIONS = {"get_quote", "get_history"}
FORBIDDEN_TERMS = {"order", "buy", "sell", "cancel", "transfer", "position", "execute"}


def run_codex_market_data(operation: str, symbol: str, period: str = "", interval: str = "", *, timeout_seconds: int = 45, codex_path: str = "/usr/bin/codex") -> dict[str, Any]:
    if operation not in ALLOWED_OPERATIONS:
        raise ValueError("unsupported market-data operation")
    if any(term in operation.lower() for term in FORBIDDEN_TERMS):
        raise ValueError("order-related operation rejected")
    prompt = (
        "Use only the enabled robinhood-trading MCP connection for read-only market data. "
        "Never place, preview, cancel, or modify orders; never access transfers or account controls. "
        f"Operation={operation}; symbol={symbol}; period={period or 'n/a'}; interval={interval or 'n/a'}. "
        "Return exactly one JSON object and no markdown. For get_quote include symbol, price, "
        "quote_timestamp, trading_date, source_type, confidence, warnings. For get_history include "
        "symbol, interval, period, generated_at, corporate_action_adjusted, split_history, "
        "dividend_history, warnings, and bars with date/open/high/low/close/adjusted_close/volume."
    )
    completed = subprocess.run([codex_path, "exec", "--skip-git-repo-check", prompt], capture_output=True,
                               text=True, timeout=timeout_seconds, check=False, env={})
    if completed.returncode != 0:
        raise RuntimeError(f"codex exec failed with exit code {completed.returncode}: {completed.stderr[-500:]}")
    text = completed.stdout.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("codex output did not contain JSON")
    payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict):
        raise RuntimeError("codex output must be one JSON object")
    forbidden_output_keys = {"token", "oauth", "authorization", "cookie", "secret", "account_number"}
    if forbidden_output_keys.intersection({str(key).lower() for key in payload}):
        raise RuntimeError("sensitive authentication/account data rejected")
    payload["provider"] = "ROBINHOOD_MCP"
    return payload
