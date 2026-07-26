"""Authenticated AI CIO paper cash funding and strategy allocation portal."""
from __future__ import annotations
import html, json, os
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from .paper_capital_allocation import append_allocation_request, build_allocation_request, discover_strategy_plugins, parse_allocation_form
from .paper_cash_account import DEFAULT_CASH_TRANSACTION_PATH, apply_paper_deposit, initialize_cash_account, read_cash_account

PAPER_TRADE_MODE=True; LIVE_TRADING_ENABLED=False; BROKER_EXECUTION_ENABLED=False; CAPITAL_MOVEMENT_ENABLED=False; INVESTOR_CONTROLS_LIVE_MODE=True
DEFAULT_REGISTRY_PATH=Path("results/enterprise_dividend_service_registry.json"); DEFAULT_CASH_PATH=Path("state/paper_cash_account.json"); DEFAULT_REQUEST_LOG=Path("state/paper_allocation_requests.jsonl")

def _load_mapping(path:Path)->dict[str,Any]:
    if not path.is_file(): return {}
    value=json.loads(path.read_text(encoding="utf-8")); return value if isinstance(value,dict) else {}

def available_cash_from_state(state:Mapping[str,Any])->float:
    for key in ("available_cash","cash_available","unallocated_cash","cash_balance","balance"):
        value=state.get(key)
        if isinstance(value,(int,float)): return round(float(value),2)
    summary=state.get("summary"); return available_cash_from_state(summary) if isinstance(summary,Mapping) else 0.0

def _cash_state(path:Path)->dict[str,Any]:
    if not path.is_file(): return {}
    try: return read_cash_account(path)
    except ValueError:
        legacy=_load_mapping(path)
        if available_cash_from_state(legacy)<0: raise ValueError("available paper cash cannot be negative")
        return legacy

def _layout(title:str,body:str,active:str)->str:
    items=(("Cash Account","/cash"),("Strategy Allocation","/allocation"),("Executive Dashboard","/executive_dashboard.html"),("Investor Dashboard","/investor_dashboard.html"))
    nav="".join(f'<a class="{"active" if n==active else ""}" href="{u}">{n}</a>' for n,u in items)
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>:root{{--purple:#5d18d6;--line:#dfe3ec;--bg:#f5f7fb;--muted:#667085}}*{{box-sizing:border-box}}body{{margin:0;font-family:Arial;background:var(--bg);color:#101828}}header{{background:linear-gradient(120deg,#07172f,#10244b);color:white;padding:24px 32px}}header h1{{margin:0}}nav{{display:flex;gap:18px;flex-wrap:wrap;padding:12px 32px;background:white;border-bottom:1px solid var(--line)}}nav a{{color:#344054;text-decoration:none;font-weight:700}}nav a.active{{color:var(--purple)}}.banner{{margin:18px 24px;padding:12px 16px;border-left:5px solid var(--purple);background:#f1eaff;font-weight:700}}main{{max-width:1180px;margin:auto;padding:0 24px 32px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-bottom:18px}}.card,.panel{{background:white;border:1px solid var(--line);border-radius:14px;box-shadow:0 4px 14px #1018280d}}.card{{padding:20px;min-height:130px}}.label{{font-weight:700;color:#344054}}.value{{font-size:28px;font-weight:800;color:var(--purple);margin-top:18px}}.two{{display:grid;grid-template-columns:1fr 1.4fr;gap:18px}}.panel{{padding:22px}}.panel h2{{margin-top:0;color:#43169a}}label{{display:block;font-weight:700;margin:14px 0 6px}}input,select{{width:100%;padding:11px;border:1px solid #cfd4dc;border-radius:8px}}button{{background:var(--purple);color:white;border:0;border-radius:9px;padding:12px 18px;font-weight:700}}.strategy{{display:grid;grid-template-columns:28px 1fr 180px;gap:12px;align-items:center;padding:16px;border-top:1px solid #e4e7ec}}.strategy input[type=checkbox]{{width:auto}}small{{display:block;color:var(--muted);margin-top:5px}}.commentary{{background:#fffaf0;border:1px solid #f4cc73;border-radius:12px;padding:18px;line-height:1.55}}.warning{{background:#fff4e5;border-left:5px solid #f79009;padding:12px;margin:16px 0}}@media(max-width:800px){{.two{{grid-template-columns:1fr}}.strategy{{grid-template-columns:28px 1fr}}.strategy .amount{{grid-column:2}}}}</style></head><body><header><h1>{html.escape(title)}</h1><p>Enterprise AI CIO investor-controlled capital portal</p></header><nav>{nav}</nav><div class='banner'>PAPER ONLY · No brokerage connection · No live orders · Only the investor can authorize future live mode</div><main>{body}</main></body></html>"""

def render_cash_account_html(account:Mapping[str,Any])->str:
    starting=float(account.get("starting_cash",0)); available=available_cash_from_state(account); reserved=float(account.get("reserved_cash",0)); allocated=float(account.get("allocated_cash",0))
    body=f"""<section class='grid'><article class='card'><div class='label'>Starting Paper Cash</div><div class='value'>${starting:,.2f}</div></article><article class='card'><div class='label'>Available Cash</div><div class='value'>${available:,.2f}</div></article><article class='card'><div class='label'>Reserved Cash</div><div class='value'>${reserved:,.2f}</div></article><article class='card'><div class='label'>Allocated Cash</div><div class='value'>${allocated:,.2f}</div></article></section><section class='two'><article class='panel'><h2>Add Simulated Capital</h2><form method='post' action='/cash/deposit'><label>Amount</label><input name='amount' type='number' min='0.01' step='0.01' required placeholder='$0.00'><label>Reason</label><select name='reason'><option value='INITIAL_PAPER_FUNDING'>Initial paper funding</option><option value='ADDITIONAL_PAPER_DEPOSIT' selected>Additional paper deposit</option><option value='PAPER_CAPITAL_ADJUSTMENT'>Paper capital adjustment</option></select><label><input style='width:auto' name='investor_confirmed' value='yes' type='checkbox' required> I confirm this is simulated paper capital.</label><p><button type='submit'>Apply Paper Cash</button></p></form></article><article class='panel'><h2>AI CIO Commentary</h2><div class='commentary'>Add investor-supplied simulated funds here, then allocate available cash across strategies recognized by the Enterprise Service Registry. A future Robinhood provider may read live cash through Agentic only after explicit investor authorization.</div><p><a href='/allocation'>Continue to Strategy Allocation →</a></p></article></section>"""
    return _layout("Enterprise Paper Cash Account",body,"Cash Account")

def render_allocation_page(cash:float,plugins:list[dict[str,Any]])->str:
    cards=[]
    for item in plugins:
        sid=html.escape(str(item.get("strategy_id"))); name=html.escape(str(item.get("display_name") or sid)); status=html.escape(str(item.get("status") or "UNKNOWN")); health=html.escape(str(item.get("health") or "UNKNOWN"))
        cards.append(f'<label class="strategy"><input type="checkbox" name="strategy" value="{sid}"><span><strong>{name}</strong><small>{status} · Health {health}</small></span><input class="amount" name="amount_{sid}" type="number" min="0" step="0.01" placeholder="$0.00"></label>')
    strategies="".join(cards) or "<p>No eligible paper strategy plugins are registered.</p>"
    body=f"""<section class='grid'><article class='card'><div class='label'>Available Paper Cash</div><div class='value'>${cash:,.2f}</div></article><article class='card'><div class='label'>Eligible Strategies</div><div class='value'>{len(plugins)}</div></article><article class='card'><div class='label'>Cash Provider</div><div class='value'>PAPER</div></article></section><section class='panel'><h2>Allocate Cash to Detected Strategies</h2><div class='warning'>Only enabled, paper-compatible strategies discovered from the Enterprise Service Registry are shown.</div><form method='post' action='/allocation/request'><label>Total cash to allocate</label><input name='requested_cash' type='number' min='0.01' max='{cash:.2f}' step='0.01' required><h2>Available Strategies</h2>{strategies}<p><button type='submit'>Record Paper Allocation Request</button></p></form></section>"""
    return _layout("Enterprise Strategy Allocation",body,"Strategy Allocation")

def _confirmation(title:str,message:str,href:str)->str: return _layout(title,f"<section class='panel'><h2>{html.escape(title)}</h2><div class='commentary'>{html.escape(message)}</div><p><a href='{href}'>Continue →</a></p></section>","Cash Account" if href=="/cash" else "Strategy Allocation")

def create_wsgi_app(*,registry_path:str|Path=DEFAULT_REGISTRY_PATH,cash_path:str|Path=DEFAULT_CASH_PATH,request_log:str|Path=DEFAULT_REQUEST_LOG,transaction_log:str|Path=DEFAULT_CASH_TRANSACTION_PATH,investor_id:str="default-investor",initial_paper_cash:Optional[float]=None)->Callable:
    registry_file,cash_file,request_file,transaction_file=Path(registry_path),Path(cash_path),Path(request_log),Path(transaction_log)
    if not cash_file.is_file() and initial_paper_cash is not None: initialize_cash_account(path=cash_file,investor_money=initial_paper_cash,investor_id=investor_id)
    def app(environ:Mapping[str,Any],start_response:Callable)->Iterable[bytes]:
        path=str(environ.get("PATH_INFO") or "/"); method=str(environ.get("REQUEST_METHOD") or "GET").upper()
        try:
            account=_cash_state(cash_file)
            if method=="GET" and path in {"/","/cash"}: payload=render_cash_account_html(account).encode(); status="200 OK"
            elif method=="POST" and path=="/cash/deposit":
                length=int(environ.get("CONTENT_LENGTH") or 0); values=parse_qs(environ["wsgi.input"].read(length).decode())
                if values.get("investor_confirmed",[""])[0]!="yes": raise ValueError("investor confirmation is required")
                tx=apply_paper_deposit(account_path=cash_file,transaction_path=transaction_file,amount=float(values.get("amount",["0"])[0]),reason=values.get("reason",["ADDITIONAL_PAPER_DEPOSIT"])[0],investor_id=investor_id)
                payload=_confirmation("Paper Cash Applied",f"${float(tx['amount']):,.2f} was added. New available balance: ${float(tx['balance_after']):,.2f}.","/allocation").encode(); status="201 Created"
            elif method=="GET" and path=="/allocation":
                plugins=discover_strategy_plugins(_load_mapping(registry_file)); payload=render_allocation_page(available_cash_from_state(account),plugins).encode(); status="200 OK"
            elif method=="POST" and path=="/allocation/request":
                length=int(environ.get("CONTENT_LENGTH") or 0); requested,allocations=parse_allocation_form(environ["wsgi.input"].read(length)); plugins=discover_strategy_plugins(_load_mapping(registry_file)); request=build_allocation_request(available_cash=available_cash_from_state(account),requested_cash=requested,allocations=allocations,strategy_plugins=plugins,investor_id=investor_id); recorded=append_allocation_request(request,request_file); payload=_confirmation("Paper Allocation Request",f"Request {request['request_id']} {'recorded' if recorded else 'already exists'} with status {request['status']}. No cash moved and no order was placed.","/allocation").encode(); status="201 Created" if recorded else "200 OK"
            else: payload=b"Not found"; status="404 Not Found"
            start_response(status,[("Content-Type","text/html; charset=utf-8"),("Content-Length",str(len(payload)))]); return [payload]
        except (ValueError,RuntimeError,json.JSONDecodeError) as exc:
            payload=("Invalid investor-controlled paper request: "+str(exc)).encode(); start_response("400 Bad Request",[("Content-Type","text/plain; charset=utf-8"),("Content-Length",str(len(payload)))]); return [payload]
    return app

def main()->int:
    host=os.environ.get("DIVIDEND_ALLOCATION_HOST","127.0.0.1"); port=int(os.environ.get("DIVIDEND_ALLOCATION_PORT","8091")); raw=os.environ.get("DIVIDEND_INITIAL_PAPER_CASH"); initial=float(raw) if raw and raw.strip() else None
    app=create_wsgi_app(registry_path=os.environ.get("DIVIDEND_STRATEGY_REGISTRY",str(DEFAULT_REGISTRY_PATH)),cash_path=os.environ.get("DIVIDEND_PAPER_CASH_STATE",str(DEFAULT_CASH_PATH)),request_log=os.environ.get("DIVIDEND_ALLOCATION_REQUEST_LOG",str(DEFAULT_REQUEST_LOG)),transaction_log=os.environ.get("DIVIDEND_CASH_TRANSACTION_LOG",str(DEFAULT_CASH_TRANSACTION_PATH)),investor_id=os.environ.get("DIVIDEND_INVESTOR_ID","default-investor"),initial_paper_cash=initial)
    print(f"Investor-controlled paper capital portal listening on http://{host}:{port}/cash")
    with make_server(host,port,app) as server: server.serve_forever()
    return 0
if __name__=="__main__": raise SystemExit(main())
