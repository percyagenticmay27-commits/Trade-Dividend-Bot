"""Authenticated AI CIO paper cash funding and strategy allocation portal."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from .paper_allocation_governance import (
    DEFAULT_ALLOCATION_TRANSACTION_LOG,
    DEFAULT_APPROVAL_LOG,
    approve_allocation_request,
)
from .paper_capital_allocation import (
    append_allocation_request,
    build_allocation_request,
    discover_strategy_plugins,
    parse_allocation_form,
)
from .paper_cash_account import (
    DEFAULT_CASH_TRANSACTION_PATH,
    apply_paper_deposit,
    initialize_cash_account,
    read_cash_account,
)
from .portal_dashboard_routes import (
    load_executive_dashboard_body,
    load_investor_dashboard_body,
    render_unavailable_dashboard,
)

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
INVESTOR_CONTROLS_LIVE_MODE = True

DEFAULT_REGISTRY_PATH = Path("results/enterprise_dividend_service_registry.json")
DEFAULT_CASH_PATH = Path("state/paper_cash_account.json")
DEFAULT_REQUEST_LOG = Path("state/paper_allocation_requests.jsonl")
DEFAULT_EXECUTIVE_DASHBOARD_HTML = Path("results/ai_cio_executive_dashboard.html")
DEFAULT_EXECUTIVE_DASHBOARD_JSON = Path("results/ai_cio_executive_dashboard.json")
DEFAULT_INVESTOR_DASHBOARD_JSON = Path("results/enterprise_investor_dashboard.json")


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def available_cash_from_state(state: Mapping[str, Any]) -> float:
    for key in ("available_cash", "cash_available", "unallocated_cash", "cash_balance", "balance"):
        value = state.get(key)
        if isinstance(value, (int, float)):
            return round(float(value), 2)
    summary = state.get("summary")
    return available_cash_from_state(summary) if isinstance(summary, Mapping) else 0.0


def _cash_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return read_cash_account(path)
    except ValueError:
        legacy = _load_mapping(path)
        if available_cash_from_state(legacy) < 0:
            raise ValueError("available paper cash cannot be negative")
        return legacy


def _layout(title: str, body: str, active: str) -> str:
    items = (
        ("Cash Account", "/cash"),
        ("Strategy Allocation", "/allocation"),
        ("Executive Dashboard", "/executive-dashboard"),
        ("Investor Dashboard", "/investor-dashboard"),
    )
    nav = "".join(f'<a class="{"active" if name == active else ""}" href="{url}">{name}</a>' for name, url in items)
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>:root{{--purple:#5d18d6;--line:#dfe3ec;--bg:#f5f7fb;--muted:#667085}}*{{box-sizing:border-box}}body{{margin:0;font-family:Arial;background:var(--bg);color:#101828}}header{{background:linear-gradient(120deg,#07172f,#10244b);color:white;padding:24px 32px}}header h1{{margin:0}}nav{{display:flex;gap:18px;flex-wrap:wrap;padding:12px 32px;background:white;border-bottom:1px solid var(--line)}}nav a{{color:#344054;text-decoration:none;font-weight:700}}nav a.active{{color:var(--purple)}}.banner{{margin:18px 24px;padding:12px 16px;border-left:5px solid var(--purple);background:#f1eaff;font-weight:700}}main{{max-width:1180px;margin:auto;padding:0 24px 32px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-bottom:18px}}.card,.panel{{background:white;border:1px solid var(--line);border-radius:14px;box-shadow:0 4px 14px #1018280d}}.card{{padding:20px;min-height:130px}}.label{{font-weight:700;color:#344054}}.value{{font-size:28px;font-weight:800;color:var(--purple);margin-top:18px}}.two{{display:grid;grid-template-columns:1fr 1.4fr;gap:18px}}.panel{{padding:22px;margin-bottom:18px}}.panel h2{{margin-top:0;color:#43169a}}label{{display:block;font-weight:700;margin:14px 0 6px}}input,select{{width:100%;padding:11px;border:1px solid #cfd4dc;border-radius:8px}}button{{background:var(--purple);color:white;border:0;border-radius:9px;padding:12px 18px;font-weight:700}}.strategy{{display:grid;grid-template-columns:28px 1fr 180px;gap:12px;align-items:center;padding:16px;border-top:1px solid #e4e7ec}}.strategy.single{{grid-template-columns:1fr 240px}}.strategy input[type=checkbox]{{width:auto}}.current-allocation{{text-align:right}}.current-allocation strong{{display:block;color:var(--purple);font-size:18px}}.proposed{{text-align:right;color:#43169a;font-weight:700}}.allocation-summary{{display:grid;grid-template-columns:repeat(3,minmax(150px,1fr));gap:12px;margin:18px 0}}.allocation-summary div{{background:#f8f5ff;border:1px solid #d9cdf5;border-radius:10px;padding:12px}}.allocation-summary strong{{display:block;color:var(--purple);font-size:18px;margin-top:5px}}.amount-wrap[hidden],.proposed[hidden]{{display:none}}small{{display:block;color:var(--muted);margin-top:5px}}.commentary{{background:#fffaf0;border:1px solid #f4cc73;border-radius:12px;padding:18px;line-height:1.55}}.warning{{background:#fff4e5;border-left:5px solid #f79009;padding:12px;margin:16px 0}}.approve{{margin-top:18px;padding:18px;border:1px solid #b9a2ef;background:#f7f3ff;border-radius:12px}}table th,table td{{padding:10px;border-bottom:1px solid var(--line)}}@media(max-width:800px){{.two{{grid-template-columns:1fr}}.strategy,.strategy.single{{grid-template-columns:1fr}}.strategy .amount-wrap{{grid-column:1}}.current-allocation,.proposed{{text-align:left}}.allocation-summary{{grid-template-columns:1fr}}}}</style></head><body><header><h1>{html.escape(title)}</h1><p>Enterprise AI CIO investor-controlled capital portal</p></header><nav>{nav}</nav><div class='banner'>PAPER ONLY · No brokerage connection · No live orders · Only the investor can authorize future live mode</div><main>{body}</main></body></html>"""


def render_cash_account_html(account: Mapping[str, Any]) -> str:
    starting = float(account.get("starting_cash", 0))
    available = available_cash_from_state(account)
    reserved = float(account.get("reserved_cash", 0))
    allocated = float(account.get("allocated_cash", 0))
    body = f"""<section class='grid'><article class='card'><div class='label'>Starting Paper Cash</div><div class='value'>${starting:,.2f}</div></article><article class='card'><div class='label'>Available Cash</div><div class='value'>${available:,.2f}</div></article><article class='card'><div class='label'>Reserved Cash</div><div class='value'>${reserved:,.2f}</div></article><article class='card'><div class='label'>Allocated Cash</div><div class='value'>${allocated:,.2f}</div></article></section><section class='two'><article class='panel'><h2>Add Simulated Capital</h2><form method='post' action='/cash/deposit'><label>Amount</label><input name='amount' type='number' min='0.01' step='0.01' required placeholder='$0.00'><label>Reason</label><select name='reason'><option value='INITIAL_PAPER_FUNDING'>Initial paper funding</option><option value='ADDITIONAL_PAPER_DEPOSIT' selected>Additional paper deposit</option><option value='PAPER_CAPITAL_ADJUSTMENT'>Paper capital adjustment</option></select><label><input style='width:auto' name='investor_confirmed' value='yes' type='checkbox' required> I confirm this is simulated paper capital.</label><p><button type='submit'>Apply Paper Cash</button></p></form></article><article class='panel'><h2>AI CIO Commentary</h2><div class='commentary'>Add investor-supplied simulated funds here, then allocate available cash across strategies recognized by the Enterprise Service Registry. A future Robinhood provider may read live cash through Agentic only after explicit investor authorization.</div><p><a href='/allocation'>Continue to Strategy Allocation →</a></p></article></section>"""
    return _layout("Enterprise Paper Cash Account", body, "Cash Account")



def allocation_for_strategy(strategy_allocations: Mapping[str, Any], strategy_id: str) -> float:
    """Resolve canonical and legacy strategy IDs without mutating stored state."""
    raw_id = str(strategy_id).strip()
    candidates = [raw_id]
    normalized = raw_id.upper().replace("_", "-")
    if normalized in {"DIVIDEND", "DIVIDEND-001"}:
        candidates.extend(("DIVIDEND-001", "DIVIDEND", "dividend"))
    for candidate in candidates:
        value = strategy_allocations.get(candidate)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0

def render_allocation_page(cash: float, plugins: list[dict[str, Any]], strategy_allocations: Optional[Mapping[str, Any]] = None) -> str:
    cards: list[str] = []
    existing = dict(strategy_allocations or {})
    for item in plugins:
        raw_sid = str(item.get("strategy_id"))
        sid = html.escape(raw_sid)
        name = html.escape(str(item.get("display_name") or sid))
        status = html.escape(str(item.get("status") or "UNKNOWN"))
        health = html.escape(str(item.get("health") or "UNKNOWN"))
        current = allocation_for_strategy(existing, raw_sid)
        cards.append(
            f'<label class="strategy" data-strategy-row>'
            f'<input type="checkbox" name="strategy" value="{sid}" data-strategy-checkbox>'
            f'<span><strong>{name}</strong><small>{status} · Health {health}</small>'
            f'<small>Currently allocated: ${current:,.2f}</small></span>'
            f'<span class="amount-wrap" data-amount-wrap hidden><input class="amount" name="amount_{sid}" '
            f'type="number" min="0.01" step="0.01" placeholder="$0.00" data-allocation-amount disabled></span>'
            f'<span class="proposed" data-proposed hidden>Proposed allocation: 100% of requested cash</span>'
            f'</label>'
        )
    strategies = "".join(cards) or "<p>No eligible paper strategy plugins are registered.</p>"
    body = f"""<section class='grid'><article class='card'><div class='label'>Available Paper Cash</div><div class='value'>${cash:,.2f}</div></article><article class='card'><div class='label'>Eligible Strategies</div><div class='value'>{len(plugins)}</div></article><article class='card'><div class='label'>Cash Provider</div><div class='value'>PAPER</div></article></section><section class='panel'><h2>Allocate Cash to Detected Strategies</h2><div class='warning'>Only enabled, paper-compatible strategies discovered from the Enterprise Service Registry are shown. Select one strategy to assign 100% automatically, or select multiple strategies to divide the request manually.</div><form id='allocation-form' method='post' action='/allocation/request'><label>Total cash to allocate</label><input id='requested-cash' name='requested_cash' type='number' min='0.01' max='{cash:.2f}' step='0.01' required><h2>Available Strategies</h2>{strategies}<section class='allocation-summary' aria-live='polite'><div>Total requested<strong id='summary-requested'>$0.00</strong></div><div>Total assigned<strong id='summary-assigned'>$0.00</strong></div><div>Remaining unassigned<strong id='summary-remaining'>$0.00</strong></div></section><p><button type='submit'>Record Paper Allocation Request</button></p></form></section><script>
(function(){{
  const form=document.getElementById('allocation-form');
  if(!form)return;
  const requested=document.getElementById('requested-cash');
  const boxes=[...form.querySelectorAll('[data-strategy-checkbox]')];
  const money=value=>'$'+(Number(value)||0).toLocaleString(undefined,{{minimumFractionDigits:2,maximumFractionDigits:2}});
  function update(){{
    const selected=boxes.filter(box=>box.checked);
    let assigned=0;
    boxes.forEach(box=>{{
      const row=box.closest('[data-strategy-row]');
      const wrap=row.querySelector('[data-amount-wrap]');
      const amount=row.querySelector('[data-allocation-amount]');
      const proposed=row.querySelector('[data-proposed]');
      const manual=selected.length>1 && box.checked;
      const automatic=selected.length===1 && box.checked;
      wrap.hidden=!manual;
      proposed.hidden=!automatic;
      amount.disabled=!manual;
      amount.required=manual;
      if(!manual)amount.value='';
      if(manual)assigned+=Number(amount.value)||0;
    }});
    const total=Number(requested.value)||0;
    if(selected.length===1)assigned=total;
    document.getElementById('summary-requested').textContent=money(total);
    document.getElementById('summary-assigned').textContent=money(assigned);
    document.getElementById('summary-remaining').textContent=money(total-assigned);
  }}
  boxes.forEach(box=>box.addEventListener('change',update));
  requested.addEventListener('input',update);
  form.querySelectorAll('[data-allocation-amount]').forEach(input=>input.addEventListener('input',update));
  form.addEventListener('submit',event=>{{
    const selected=boxes.filter(box=>box.checked);
    if(selected.length===0){{event.preventDefault();alert('Select at least one strategy.');return;}}
    if(selected.length>1){{
      const total=Number(requested.value)||0;
      const assigned=selected.reduce((sum,box)=>sum+(Number(box.closest('[data-strategy-row]').querySelector('[data-allocation-amount]').value)||0),0);
      if(Math.round(total*100)!==Math.round(assigned*100)){{event.preventDefault();alert('Strategy allocations must equal Total cash to allocate.');}}
    }}
  }});
  update();
}})();
</script>"""
    return _layout("Enterprise Strategy Allocation", body, "Strategy Allocation")


def _confirmation(title: str, message: str, href: str) -> str:
    return _layout(title, f"<section class='panel'><h2>{html.escape(title)}</h2><div class='commentary'>{html.escape(message)}</div><p><a href='{href}'>Continue →</a></p></section>", "Cash Account" if href == "/cash" else "Strategy Allocation")


def _allocation_review(request: Mapping[str, Any], recorded: bool) -> str:
    request_id = html.escape(str(request.get("request_id") or ""))
    amount = float(request.get("requested_cash", 0) or 0)
    allocations = request.get("allocations") if isinstance(request.get("allocations"), list) else []
    rows = "".join(
        f"<li>{html.escape(str(item.get('strategy_name') or item.get('strategy_id') or 'Strategy'))}: <strong>${float(item.get('amount', 0)):,.2f}</strong></li>"
        for item in allocations if isinstance(item, Mapping)
    )
    body = f"""<section class='panel'><h2>Paper Allocation Request</h2><div class='commentary'>Request {request_id} {'recorded' if recorded else 'already exists'} with status PENDING_GOVERNANCE_REVIEW. No cash has been transferred and no order has been placed.</div><h3>Requested paper allocation</h3><p>Total: <strong>${amount:,.2f}</strong></p><ul>{rows}</ul><div class='approve'><h3>Investor Governance Approval</h3><p>Approve this request to update simulated available and allocated cash. This remains paper-only and cannot place an order.</p><form method='post' action='/allocation/approve'><input type='hidden' name='request_id' value='{request_id}'><label><input style='width:auto' type='checkbox' name='investor_confirmed' value='yes' required> I approve this simulated paper allocation.</label><p><button type='submit'>Approve and Apply Paper Allocation</button></p></form></div><p><a href='/allocation'>Return without approving →</a></p></section>"""
    return _layout("Paper Allocation Governance Review", body, "Strategy Allocation")


def create_wsgi_app(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    cash_path: str | Path = DEFAULT_CASH_PATH,
    request_log: str | Path = DEFAULT_REQUEST_LOG,
    transaction_log: str | Path = DEFAULT_CASH_TRANSACTION_PATH,
    approval_log: str | Path = DEFAULT_APPROVAL_LOG,
    allocation_transaction_log: str | Path = DEFAULT_ALLOCATION_TRANSACTION_LOG,
    executive_dashboard_html: str | Path = DEFAULT_EXECUTIVE_DASHBOARD_HTML,
    executive_dashboard_json: str | Path = DEFAULT_EXECUTIVE_DASHBOARD_JSON,
    investor_dashboard_json: str | Path = DEFAULT_INVESTOR_DASHBOARD_JSON,
    investor_id: str = "default-investor",
    initial_paper_cash: Optional[float] = None,
) -> Callable:
    registry_file = Path(registry_path)
    cash_file = Path(cash_path)
    request_file = Path(request_log)
    transaction_file = Path(transaction_log)
    approval_file = Path(approval_log)
    allocation_transaction_file = Path(allocation_transaction_log)
    executive_html_file = Path(executive_dashboard_html)
    executive_json_file = Path(executive_dashboard_json)
    investor_json_file = Path(investor_dashboard_json)
    if not cash_file.is_file() and initial_paper_cash is not None:
        initialize_cash_account(path=cash_file, investor_money=initial_paper_cash, investor_id=investor_id)

    def app(environ: Mapping[str, Any], start_response: Callable) -> Iterable[bytes]:
        path = str(environ.get("PATH_INFO") or "/")
        method = str(environ.get("REQUEST_METHOD") or "GET").upper()
        try:
            account = _cash_state(cash_file)
            if method == "GET" and path in {"/", "/cash"}:
                payload = render_cash_account_html(account).encode()
                status = "200 OK"
            elif method == "GET" and path == "/executive-dashboard":
                try:
                    dashboard, complete_document = load_executive_dashboard_body(
                        html_path=executive_html_file,
                        json_path=executive_json_file,
                    )
                    payload = dashboard.encode("utf-8") if complete_document else _layout("AI CIO Executive Dashboard", dashboard, "Executive Dashboard").encode("utf-8")
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    payload = _layout(
                        "AI CIO Executive Dashboard",
                        render_unavailable_dashboard("Executive Dashboard Unavailable", f"Executive dashboard artifact could not be read: {exc}"),
                        "Executive Dashboard",
                    ).encode("utf-8")
                status = "200 OK"
            elif method == "GET" and path == "/investor-dashboard":
                try:
                    dashboard, _ = load_investor_dashboard_body(json_path=investor_json_file)
                    payload = _layout("Enterprise Investor Dashboard", dashboard, "Investor Dashboard").encode("utf-8")
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    payload = _layout(
                        "Enterprise Investor Dashboard",
                        render_unavailable_dashboard("Investor Dashboard Unavailable", f"Investor dashboard artifact could not be read: {exc}"),
                        "Investor Dashboard",
                    ).encode("utf-8")
                status = "200 OK"
            elif method == "POST" and path == "/cash/deposit":
                length = int(environ.get("CONTENT_LENGTH") or 0)
                values = parse_qs(environ["wsgi.input"].read(length).decode())
                if values.get("investor_confirmed", [""])[0] != "yes":
                    raise ValueError("investor confirmation is required")
                transaction = apply_paper_deposit(
                    account_path=cash_file,
                    transaction_path=transaction_file,
                    amount=float(values.get("amount", ["0"])[0]),
                    reason=values.get("reason", ["ADDITIONAL_PAPER_DEPOSIT"])[0],
                    investor_id=investor_id,
                )
                payload = _confirmation("Paper Cash Applied", f"${float(transaction['amount']):,.2f} was added. New available balance: ${float(transaction['balance_after']):,.2f}.", "/allocation").encode()
                status = "201 Created"
            elif method == "GET" and path == "/allocation":
                plugins = discover_strategy_plugins(_load_mapping(registry_file))
                strategy_allocations = account.get("strategy_allocations") if isinstance(account.get("strategy_allocations"), Mapping) else {}
                payload = render_allocation_page(available_cash_from_state(account), plugins, strategy_allocations).encode()
                status = "200 OK"
            elif method == "POST" and path == "/allocation/request":
                length = int(environ.get("CONTENT_LENGTH") or 0)
                requested, allocations = parse_allocation_form(environ["wsgi.input"].read(length))
                plugins = discover_strategy_plugins(_load_mapping(registry_file))
                request = build_allocation_request(
                    available_cash=available_cash_from_state(account),
                    requested_cash=requested,
                    allocations=allocations,
                    strategy_plugins=plugins,
                    investor_id=investor_id,
                )
                recorded = append_allocation_request(request, request_file)
                payload = _allocation_review(request, recorded).encode()
                status = "201 Created" if recorded else "200 OK"
            elif method == "POST" and path == "/allocation/approve":
                length = int(environ.get("CONTENT_LENGTH") or 0)
                values = parse_qs(environ["wsgi.input"].read(length).decode())
                decision = approve_allocation_request(
                    request_id=values.get("request_id", [""])[0],
                    request_log=request_file,
                    account_path=cash_file,
                    approval_log=approval_file,
                    transaction_log=allocation_transaction_file,
                    investor_id=investor_id,
                    investor_confirmed=values.get("investor_confirmed", [""])[0] == "yes",
                )
                refreshed = read_cash_account(cash_file)
                payload = _confirmation(
                    "Paper Allocation Applied",
                    f"Request {decision['request_id']} was approved and applied to the paper account. Available cash: ${float(refreshed['available_cash']):,.2f}. Allocated cash: ${float(refreshed['allocated_cash']):,.2f}. No order was placed.",
                    "/allocation",
                ).encode()
                status = "200 OK"
            else:
                payload = b"Not found"
                status = "404 Not Found"
            start_response(status, [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload)))])
            return [payload]
        except (ValueError, RuntimeError, PermissionError, json.JSONDecodeError) as exc:
            payload = ("Invalid investor-controlled paper request: " + str(exc)).encode()
            start_response("400 Bad Request", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(payload)))])
            return [payload]

    return app


def main() -> int:
    host = os.environ.get("DIVIDEND_ALLOCATION_HOST", "127.0.0.1")
    port = int(os.environ.get("DIVIDEND_ALLOCATION_PORT", "8091"))
    raw = os.environ.get("DIVIDEND_INITIAL_PAPER_CASH")
    initial = float(raw) if raw and raw.strip() else None
    app = create_wsgi_app(
        registry_path=os.environ.get("DIVIDEND_STRATEGY_REGISTRY", str(DEFAULT_REGISTRY_PATH)),
        cash_path=os.environ.get("DIVIDEND_PAPER_CASH_STATE", str(DEFAULT_CASH_PATH)),
        request_log=os.environ.get("DIVIDEND_ALLOCATION_REQUEST_LOG", str(DEFAULT_REQUEST_LOG)),
        transaction_log=os.environ.get("DIVIDEND_CASH_TRANSACTION_LOG", str(DEFAULT_CASH_TRANSACTION_PATH)),
        approval_log=os.environ.get("DIVIDEND_ALLOCATION_APPROVAL_LOG", str(DEFAULT_APPROVAL_LOG)),
        allocation_transaction_log=os.environ.get("DIVIDEND_ALLOCATION_TRANSACTION_LOG", str(DEFAULT_ALLOCATION_TRANSACTION_LOG)),
        executive_dashboard_html=os.environ.get("DIVIDEND_EXECUTIVE_DASHBOARD_HTML", str(DEFAULT_EXECUTIVE_DASHBOARD_HTML)),
        executive_dashboard_json=os.environ.get("DIVIDEND_EXECUTIVE_DASHBOARD_JSON", str(DEFAULT_EXECUTIVE_DASHBOARD_JSON)),
        investor_dashboard_json=os.environ.get("DIVIDEND_INVESTOR_DASHBOARD_JSON", str(DEFAULT_INVESTOR_DASHBOARD_JSON)),
        investor_id=os.environ.get("DIVIDEND_INVESTOR_ID", "default-investor"),
        initial_paper_cash=initial,
    )
    print(f"Investor-controlled paper capital portal listening on http://{host}:{port}/cash")
    with make_server(host, port, app) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
