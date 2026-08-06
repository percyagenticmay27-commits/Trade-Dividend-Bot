"""Governed paper-cash allocation requests for registered strategy plugins.

This module never moves money, places orders, or contacts a broker. It records
an immutable investor allocation request that downstream paper-only strategy
services may consume after governance review.
"""
from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
from urllib.parse import parse_qs

MODULE_NAME = "paper_capital_allocation"
MODULE_VERSION = "1.0.1"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

ELIGIBLE_STATUSES = {"ONLINE", "ENABLED", "AVAILABLE", "HEALTHY", "READY", "REGISTERED"}
REQUEST_STATUS = "PENDING_GOVERNANCE_REVIEW"


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def discover_strategy_plugins(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return paper-compatible strategies discovered from flexible registry shapes."""
    candidates: list[Any] = []
    for key in ("strategy_plugins", "strategies", "services", "registered_services"):
        value = registry.get(key)
        if isinstance(value, list):
            candidates.extend(value)
        elif isinstance(value, Mapping):
            candidates.extend(value.values())

    discovered: dict[str, dict[str, Any]] = {}
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        strategy_id = str(
            raw.get("strategy_id")
            or raw.get("plugin_id")
            or raw.get("service_id")
            or raw.get("name")
            or ""
        ).strip()
        if not strategy_id:
            continue
        kind = str(raw.get("service_type") or raw.get("plugin_type") or raw.get("type") or "").upper()
        explicitly_strategy = bool(raw.get("strategy_plugin")) or "STRATEGY" in kind or "DIVIDEND" in strategy_id.upper()
        if not explicitly_strategy:
            continue
        status = str(raw.get("status") or raw.get("runtime_status") or "AVAILABLE").upper()
        enabled = bool(raw.get("enabled", True))
        paper_compatible = bool(raw.get("paper_trade_mode", raw.get("paper_compatible", True)))
        if not enabled or not paper_compatible or status not in ELIGIBLE_STATUSES:
            continue
        discovered[strategy_id] = {
            "strategy_id": strategy_id,
            "display_name": str(raw.get("display_name") or raw.get("name") or strategy_id),
            "status": status,
            "version": str(raw.get("version") or raw.get("module_version") or "unknown"),
            "health": str(raw.get("health") or raw.get("health_status") or "UNKNOWN").upper(),
            "paper_trade_mode": True,
        }
    return [discovered[key] for key in sorted(discovered)]


def build_allocation_request(
    *,
    available_cash: float,
    requested_cash: float,
    allocations: Mapping[str, float],
    strategy_plugins: Sequence[Mapping[str, Any]],
    investor_id: str = "default-investor",
    created_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Validate and build a deterministic immutable paper allocation request."""
    available = round(float(available_cash), 2)
    requested = round(float(requested_cash), 2)
    if available < 0:
        raise ValueError("available_cash cannot be negative")
    if requested <= 0:
        raise ValueError("requested_cash must be greater than zero")
    if requested > available:
        raise ValueError("requested_cash cannot exceed available_cash")

    eligible = {str(item.get("strategy_id")): dict(item) for item in strategy_plugins}
    normalized: dict[str, float] = {}
    for strategy_id, amount in allocations.items():
        value = round(float(amount), 2)
        if value <= 0:
            continue
        if strategy_id not in eligible:
            raise ValueError(f"strategy is not registered and eligible: {strategy_id}")
        normalized[strategy_id] = value
    if not normalized:
        raise ValueError("at least one strategy allocation is required")
    allocated_total = round(sum(normalized.values()), 2)
    if allocated_total != requested:
        raise ValueError("strategy allocations must equal requested_cash")

    created = created_at_utc or _now_utc()
    identity = json.dumps(
        {
            "investor_id": investor_id,
            "created_at_utc": created,
            "requested_cash": requested,
            "allocations": normalized,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    request_id = "PAR-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16].upper()
    return {
        "request_id": request_id,
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": created,
        "investor_id": investor_id,
        "status": REQUEST_STATUS,
        "available_cash_before_request": available,
        "requested_cash": requested,
        "unassigned_cash_after_request": round(available - requested, 2),
        "allocations": [
            {
                "strategy_id": strategy_id,
                "strategy_name": eligible[strategy_id].get("display_name", strategy_id),
                "amount": amount,
                "percentage_of_request": round((amount / requested) * 100, 2),
            }
            for strategy_id, amount in sorted(normalized.items())
        ],
        "governance": {
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "capital_movement_enabled": False,
            "automatic_activation_allowed": False,
            "investor_confirmation_recorded": True,
            "governance_review_required": True,
        },
    }


def append_allocation_request(request: Mapping[str, Any], path: str | Path) -> bool:
    """Append once to a JSONL audit log. Return False for an existing request ID."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    request_id = str(request.get("request_id") or "")
    if not request_id:
        raise ValueError("request_id is required")
    if destination.exists():
        for line in destination.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("request_id") == request_id:
                return False
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(request), sort_keys=True) + "\n")
    return True


def render_allocation_html(*, available_cash: float, strategy_plugins: Sequence[Mapping[str, Any]]) -> str:
    """Render a secure-server-hosted form populated only from registered plugins."""
    cards = []
    single_strategy = len(strategy_plugins) == 1
    for item in strategy_plugins:
        sid = html.escape(str(item.get("strategy_id")))
        name = html.escape(str(item.get("display_name") or sid))
        status = html.escape(str(item.get("status") or "UNKNOWN"))
        health = html.escape(str(item.get("health") or "UNKNOWN"))
        if single_strategy:
            cards.append(
                f'<div class="strategy"><input type="hidden" name="strategy" value="{sid}">'
                f'<span><strong>{name}</strong><small>{status} · Health {health}</small></span>'
                '<span class="automatic"><strong>100% of request</strong><small>Automatically assigned from the total above</small></span></div>'
            )
        else:
            cards.append(
                f'<label class="strategy"><input type="checkbox" name="strategy" value="{sid}">'
                f'<span><strong>{name}</strong><small>{status} · Health {health}</small></span>'
                f'<input class="amount" name="amount_{sid}" type="number" min="0" step="0.01" placeholder="$0.00"></label>'
            )
    strategies = "".join(cards) or '<p class="empty">No eligible paper strategy plugins are registered.</p>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paper Capital Allocation</title><style>
body{{margin:0;font-family:Arial;background:#f5f7fb;color:#101828}}header{{background:#081a39;color:white;padding:24px 32px}}main{{max-width:980px;margin:24px auto;padding:0 18px}}.panel{{background:white;border:1px solid #dfe3ec;border-radius:16px;padding:24px;box-shadow:0 5px 18px #10182812}}.cash{{font-size:32px;color:#5d18d6;font-weight:800}}.strategy{{display:grid;grid-template-columns:{'1fr 210px' if single_strategy else '28px 1fr 160px'};gap:12px;align-items:center;padding:16px;border-top:1px solid #e4e7ec}}small{{display:block;color:#667085;margin-top:5px}}input{{padding:10px;border:1px solid #cfd4dc;border-radius:8px}}button{{background:#5d18d6;color:white;border:0;border-radius:9px;padding:12px 18px;font-weight:700}}.warning{{background:#fff4e5;border-left:5px solid #f79009;padding:12px;margin:16px 0}}.automatic{{text-align:right}}@media(max-width:650px){{.strategy{{grid-template-columns:1fr}}.amount{{grid-column:1}}.automatic{{text-align:left}}}}
</style></head><body><header><h1>Enterprise Paper Capital Allocation</h1><p>Choose how much simulated cash to assign to registered strategy plugins.</p></header><main><div class="panel"><p>Available paper cash</p><div class="cash">${float(available_cash):,.2f}</div><div class="warning"><strong>PAPER ONLY.</strong> Submitting this form records an immutable allocation request. It does not transfer cash, place an order, or activate a strategy automatically.</div><form method="post" action="/allocation/request"><label>Cash to allocate<br><input id="requested" name="requested_cash" type="number" min="0.01" max="{float(available_cash):.2f}" step="0.01" required></label><h2>Available strategies</h2>{strategies}<p><button type="submit">Review and record paper allocation</button></p></form></div></main></body></html>"""


def parse_allocation_form(body: bytes) -> tuple[float, dict[str, float]]:
    values = parse_qs(body.decode("utf-8"), keep_blank_values=False)
    requested = float(values.get("requested_cash", ["0"])[0])
    selected = values.get("strategy", [])
    allocations: dict[str, float] = {}
    for sid in selected:
        raw_amount = values.get(f"amount_{sid}", [""])[0]
        amount = float(raw_amount) if str(raw_amount).strip() else 0.0
        allocations[sid] = requested if len(selected) == 1 and amount <= 0 else amount
    return requested, allocations
