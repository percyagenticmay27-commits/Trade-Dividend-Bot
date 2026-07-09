"""
Portfolio Construction Engine for the Dividend Bot.

Builds a paper-only model portfolio from allocation candidates while enforcing
position count, concentration, cash shield, and deferred-candidate rules. This
module never places orders or mutates live portfolio state.
"""
from __future__ import annotations

import csv, json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME="portfolio_construction_engine"
MODULE_VERSION="1.0.0"
SCHEMA_VERSION="1.0"
GENERATED_BY="Agentic-Robin-Dividend.bot"
BOT_NAME="Agentic Robin Dividend Bot"
BOT_TYPE="paper_dividend_etf_management"
PAPER_TRADE_MODE=True
LIVE_TRADING_ENABLED=False
BROKER_EXECUTION_ENABLED=False
REPORTING_ONLY=True
CASH_SHIELD_SYMBOL="SGOV"
INCLUDED="INCLUDED"
DEFERRED="DEFERRED"
CASH_SHIELD="CASH_SHIELD"
REJECTED="REJECTED"
SUPPORTED_CONSTRUCTION_STATUSES=[INCLUDED,DEFERRED,CASH_SHIELD,REJECTED]
SUPPORTED_RISK_STATUSES=["OK","WARNING","ERROR"]
DEFAULT_MAX_POSITION_PCT=0.40
DEFAULT_MIN_POSITION_DOLLARS=75.0
DEFAULT_CASH_RESERVE_PCT=0.20
SAFETY_GUARANTEES=["paper_trade_mode is enforced as True","reporting_only is enforced as True","live_trading_enabled is enforced as False","broker_execution_enabled is enforced as False","no Robinhood execution is performed","no brokerage execution is performed","no order placement is performed","no live portfolio state mutation is performed"]
CONSTRUCTION_RULES=["Include only allocations with allocation_action=ALLOCATE and dollars meeting minimum size.","Defer candidates that exceed target holding count or fail practical sizing rules.","Enforce maximum position concentration.","Always include a cash shield allocation when cash reserve target is greater than zero."]
HOLDING_FIELDS=["symbol","opportunity_name","construction_status","target_allocation_dollars","target_allocation_pct","allocation_score","allocation_priority","risk_status","notes"]
REPORT_REQUIRED_FIELDS=["bot_name","bot_type","module_name","module_version","schema_version","generated_by","generated_at_utc","paper_trade_mode","live_trading_enabled","broker_execution_enabled","reporting_only","portfolio_value","cash_shield_symbol","cash_reserve_target_pct","cash_reserve_target_dollars","max_position_pct","min_position_dollars","target_holding_count","constructed_holdings","deferred_candidates","rejected_candidates","holding_count","deferred_count","rejected_count","total_allocated_dollars","total_allocated_pct","risk_status","warnings","errors","construction_rules","safety_guarantees"]

@dataclass(frozen=True)
class ConstructedHolding:
    symbol:str
    opportunity_name:str=""
    construction_status:str=INCLUDED
    target_allocation_dollars:float=0.0
    target_allocation_pct:float=0.0
    allocation_score:float=0.0
    allocation_priority:int=0
    risk_status:str="OK"
    notes:str=""

@dataclass(frozen=True)
class PortfolioConstructionReport:
    bot_name:str; bot_type:str; module_name:str; module_version:str; schema_version:str; generated_by:str; generated_at_utc:str
    paper_trade_mode:bool; live_trading_enabled:bool; broker_execution_enabled:bool; reporting_only:bool
    portfolio_value:float; cash_shield_symbol:str; cash_reserve_target_pct:float; cash_reserve_target_dollars:float; max_position_pct:float; min_position_dollars:float; target_holding_count:int
    constructed_holdings:List[Dict[str,Any]]; deferred_candidates:List[Dict[str,Any]]; rejected_candidates:List[Dict[str,Any]]
    holding_count:int; deferred_count:int; rejected_count:int; total_allocated_dollars:float; total_allocated_pct:float; risk_status:str; warnings:List[str]; errors:List[str]; construction_rules:List[str]; safety_guarantees:List[str]

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def _num(v,default=0.0): return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) else default
def _clamp(v,lo,hi): return max(lo,min(hi,_num(v,lo)))
def _upper(v): return v.strip().upper() if isinstance(v,str) and v.strip() else "UNKNOWN"

def _normalize_allocation(row:Mapping[str,Any])->Dict[str,Any]:
    return {"symbol":_upper(row.get("symbol","UNKNOWN")),"opportunity_name":str(row.get("opportunity_name","")),"target_allocation_dollars":max(0.0,_num(row.get("target_allocation_dollars",0))),"allocation_score":_clamp(row.get("allocation_score",0),0,100),"allocation_priority":int(_num(row.get("allocation_priority",0),0)),"allocation_action":row.get("allocation_action","UNKNOWN"),"notes":str(row.get("notes",""))}

def construct_portfolio(allocations:Iterable[Mapping[str,Any]], portfolio_value:float=500.0, cash_reserve_pct:float=DEFAULT_CASH_RESERVE_PCT, max_position_pct:float=DEFAULT_MAX_POSITION_PCT, min_position_dollars:float=DEFAULT_MIN_POSITION_DOLLARS, target_holding_count:int=2)->Dict[str,List[Dict[str,Any]]]:
    if portfolio_value<=0: raise ValueError("portfolio_value must be positive")
    max_dollars=portfolio_value*max_position_pct
    normalized=sorted([_normalize_allocation(a) for a in allocations], key=lambda r:(-r["allocation_score"], r["symbol"]))
    holdings=[]; deferred=[]; rejected=[]
    for row in normalized:
        dollars=row["target_allocation_dollars"]
        if row["allocation_action"]!="ALLOCATE":
            row["construction_status"]=DEFERRED; row["risk_status"]="WARNING"; deferred.append(row); continue
        if dollars < min_position_dollars:
            row["construction_status"]=REJECTED; row["risk_status"]="ERROR"; row["notes"]=(row["notes"]+" Below minimum position size.").strip(); rejected.append(row); continue
        if len(holdings)>=target_holding_count:
            row["construction_status"]=DEFERRED; row["risk_status"]="WARNING"; row["notes"]=(row["notes"]+" Deferred after target holding count reached.").strip(); deferred.append(row); continue
        capped=min(dollars,max_dollars)
        notes=row["notes"]
        risk="OK"
        if capped<dollars:
            notes=(notes+" Capped by max position limit.").strip(); risk="WARNING"
        holdings.append(asdict(ConstructedHolding(symbol=row["symbol"],opportunity_name=row["opportunity_name"],target_allocation_dollars=round(capped,2),target_allocation_pct=round(capped/portfolio_value,4),allocation_score=row["allocation_score"],allocation_priority=len(holdings)+1,risk_status=risk,notes=notes)))
    cash=round(portfolio_value*cash_reserve_pct,2)
    if cash>0:
        holdings.append(asdict(ConstructedHolding(symbol=CASH_SHIELD_SYMBOL,opportunity_name="Cash Shield",construction_status=CASH_SHIELD,target_allocation_dollars=cash,target_allocation_pct=round(cash/portfolio_value,4),allocation_score=100.0,allocation_priority=999,risk_status="OK",notes="Required cash shield reserve.")))
    return {"holdings":holdings,"deferred":deferred,"rejected":rejected}

def build_portfolio_construction_report(allocations:Iterable[Mapping[str,Any]]|None=None, portfolio_value:float=500.0, cash_reserve_pct:float=DEFAULT_CASH_RESERVE_PCT, max_position_pct:float=DEFAULT_MAX_POSITION_PCT, min_position_dollars:float=DEFAULT_MIN_POSITION_DOLLARS, target_holding_count:int=2)->Dict[str,Any]:
    built=construct_portfolio(list(allocations or []),portfolio_value,cash_reserve_pct,max_position_pct,min_position_dollars,target_holding_count)
    allocated=round(sum(h["target_allocation_dollars"] for h in built["holdings"]),2)
    warnings=[]
    if not allocations: warnings.append("No allocations supplied; generated valid empty model portfolio with cash shield only.")
    if allocated>portfolio_value: warnings.append("Constructed portfolio allocations exceed portfolio value; review caps and cash reserve.")
    risk="WARNING" if warnings or built["deferred"] else "OK"
    if built["rejected"] or allocated>portfolio_value: risk="ERROR"
    payload=asdict(PortfolioConstructionReport(BOT_NAME,BOT_TYPE,MODULE_NAME,MODULE_VERSION,SCHEMA_VERSION,GENERATED_BY,_now(),True,False,False,True,float(portfolio_value),CASH_SHIELD_SYMBOL,float(cash_reserve_pct),round(portfolio_value*cash_reserve_pct,2),float(max_position_pct),float(min_position_dollars),int(target_holding_count),built["holdings"],built["deferred"],built["rejected"],len(built["holdings"]),len(built["deferred"]),len(built["rejected"]),allocated,round(allocated/portfolio_value,4),risk,warnings,[],CONSTRUCTION_RULES,SAFETY_GUARANTEES))
    validate_portfolio_construction_report(payload)
    return payload

def validate_portfolio_construction_report(payload:Any)->bool:
    if not isinstance(payload,Mapping): raise ValueError("payload must be mapping")
    for f in REPORT_REQUIRED_FIELDS:
        if f not in payload: raise ValueError(f"missing required field: {f}")
    for k,v in {"paper_trade_mode":True,"live_trading_enabled":False,"broker_execution_enabled":False,"reporting_only":True}.items():
        if payload[k] is not v: raise ValueError(f"{k} must be {v}")
    if payload["cash_shield_symbol"]!=CASH_SHIELD_SYMBOL: raise ValueError("cash_shield_symbol must be SGOV")
    if payload["risk_status"] not in SUPPORTED_RISK_STATUSES: raise ValueError("risk_status unsupported")
    for n in ["portfolio_value","cash_reserve_target_pct","cash_reserve_target_dollars","max_position_pct","min_position_dollars","total_allocated_dollars","total_allocated_pct"]:
        if not isinstance(payload[n],(int,float)) or isinstance(payload[n],bool) or payload[n]<0: raise ValueError(f"{n} must be non-negative number")
    if not isinstance(payload["target_holding_count"],int) or payload["target_holding_count"]<=0: raise ValueError("target_holding_count must be positive int")
    for lf in ["constructed_holdings","deferred_candidates","rejected_candidates","warnings","errors","construction_rules","safety_guarantees"]:
        if not isinstance(payload[lf],list): raise ValueError(f"{lf} must be list")
    if payload["holding_count"]!=len(payload["constructed_holdings"]): raise ValueError("holding_count mismatch")
    if payload["deferred_count"]!=len(payload["deferred_candidates"]): raise ValueError("deferred_count mismatch")
    if payload["rejected_count"]!=len(payload["rejected_candidates"]): raise ValueError("rejected_count mismatch")
    for row in payload["constructed_holdings"]:
        for f in HOLDING_FIELDS:
            if f not in row: raise ValueError(f"holding missing {f}")
        if row["construction_status"] not in SUPPORTED_CONSTRUCTION_STATUSES: raise ValueError("construction_status unsupported")
        if row["risk_status"] not in SUPPORTED_RISK_STATUSES: raise ValueError("holding risk_status unsupported")
        if row["symbol"]!=row["symbol"].upper() or not row["symbol"].strip(): raise ValueError("symbol must be uppercase")
    return True

def write_portfolio_construction_report_json(path:str="portfolio_construction_report.json")->Dict[str,Any]:
    p=build_portfolio_construction_report(); Path(path).write_text(json.dumps(p,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return p

def read_portfolio_construction_report_json(path:str="portfolio_construction_report.json")->Dict[str,Any]:
    p=json.loads(Path(path).read_text(encoding="utf-8")); validate_portfolio_construction_report(p); return p

def write_portfolio_construction_report_csv(path:str="portfolio_construction_report.csv")->Dict[str,Any]:
    p=build_portfolio_construction_report();
    with Path(path).open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=HOLDING_FIELDS); w.writeheader(); [w.writerow({f:r.get(f,"") for f in HOLDING_FIELDS}) for r in p["constructed_holdings"]]
    return p

def format_portfolio_construction_report_markdown(payload:Mapping[str,Any])->str:
    validate_portfolio_construction_report(payload)
    lines=["# Portfolio Construction Report","",f"- Portfolio Value: ${payload['portfolio_value']:.2f}",f"- Risk Status: {payload['risk_status']}",f"- Holding Count: {payload['holding_count']}","","## Constructed Holdings","","| Symbol | Status | Dollars | Percent | Risk |","|---|---|---:|---:|---|"]
    for r in payload["constructed_holdings"]: lines.append(f"| {r['symbol']} | {r['construction_status']} | {r['target_allocation_dollars']} | {r['target_allocation_pct']} | {r['risk_status']} |")
    lines += ["","## Construction Rules"]+[f"- {x}" for x in payload["construction_rules"]]+["","## Safety Guarantees"]+[f"- {x}" for x in payload["safety_guarantees"]]
    return "\n".join(lines)+"\n"

def write_portfolio_construction_report_markdown(path:str="portfolio_construction_report.md")->Dict[str,Any]:
    p=build_portfolio_construction_report(); Path(path).write_text(format_portfolio_construction_report_markdown(p),encoding="utf-8"); return p

if __name__=="__main__":
    write_portfolio_construction_report_json(); write_portfolio_construction_report_csv(); write_portfolio_construction_report_markdown()
