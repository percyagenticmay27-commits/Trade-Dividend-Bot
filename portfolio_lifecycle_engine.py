"""
Portfolio Lifecycle Engine for the Dividend Bot.

Daily paper-only orchestration layer that summarizes holdings, rankings, sell
signals, allocation, construction, rebalance, reinvestment, and SGOV reserve
state into one lifecycle action report. No orders are placed.
"""
from __future__ import annotations

import csv, json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME="portfolio_lifecycle_engine"
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
SUPPORTED_ACTIONS=["HOLD","EXIT_TO_SGOV","REENTER","REALLOCATE","INCREASE","REDUCE","REINVEST","WATCH","NO_ACTION"]
SUPPORTED_RANKS=["A","B","C","D","E","F"]
SUPPORTED_REGIMES=["STRONG_BULL","BULL","NEUTRAL","BEAR","STRONG_BEAR","HIGH_VOLATILITY","UNKNOWN"]
MASTER_SCORE_WEIGHTS={"opportunity_score":30,"conviction_score":25,"momentum_score":20,"entry_score":10,"technical_score":10,"market_regime_support":5}
SAFETY_GUARANTEES=["paper_trade_mode is enforced as True","reporting_only is enforced as True","live_trading_enabled is enforced as False","broker_execution_enabled is enforced as False","no Robinhood execution is performed","no brokerage execution is performed","no order placement is performed","daily lifecycle actions are recommendations only"]
LIFECYCLE_RULES=["Balanced income plus growth is the default objective.","Every stock, ETF, or pair competes on merit.","A valid sale signal is required before capital leaves a holding.","Released capital is staged in SGOV before re-entry or reassignment.","Dividends follow self-funding rules.","Cash reserve adapts to market regime."]
ACTION_FIELDS=["symbol","previous_rank","current_rank","master_score","allocation_pct","allocation_dollars","lifecycle_action","reason","expected_monthly_income","expected_annual_income"]
REPORT_REQUIRED_FIELDS=["bot_name","bot_type","module_name","module_version","schema_version","generated_by","generated_at_utc","paper_trade_mode","live_trading_enabled","broker_execution_enabled","reporting_only","market_regime","portfolio_value","cash_balance","cash_reserve_target_pct","cash_reserve_target_dollars","available_excess_cash","holdings_reviewed","lifecycle_actions","action_count","income_summary","capital_summary","warnings","errors","lifecycle_rules","safety_guarantees"]

@dataclass(frozen=True)
class LifecycleHolding:
    symbol:str
    allocation_dollars:float=0.0
    allocation_pct:float=0.0
    opportunity_score:float=0.0
    conviction_score:float=0.0
    previous_conviction_score:float=0.0
    momentum_score:float=0.0
    entry_score:float=0.0
    technical_score:float=0.0
    market_regime_support:float=0.0
    previous_master_score:float=0.0
    expected_monthly_income:float=0.0
    expected_annual_income:float=0.0
    sale_signal:bool=False

@dataclass(frozen=True)
class LifecycleAction:
    symbol:str
    previous_rank:str
    current_rank:str
    master_score:float
    allocation_pct:float
    allocation_dollars:float
    lifecycle_action:str
    reason:List[str]=field(default_factory=list)
    expected_monthly_income:float=0.0
    expected_annual_income:float=0.0

@dataclass(frozen=True)
class PortfolioLifecycleReport:
    bot_name:str; bot_type:str; module_name:str; module_version:str; schema_version:str; generated_by:str; generated_at_utc:str
    paper_trade_mode:bool; live_trading_enabled:bool; broker_execution_enabled:bool; reporting_only:bool
    market_regime:str; portfolio_value:float; cash_balance:float; cash_reserve_target_pct:float; cash_reserve_target_dollars:float; available_excess_cash:float
    holdings_reviewed:int; lifecycle_actions:List[Dict[str,Any]]; action_count:int; income_summary:Dict[str,float]; capital_summary:Dict[str,float]; warnings:List[str]; errors:List[str]; lifecycle_rules:List[str]; safety_guarantees:List[str]

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def _num(v,d=0.0): return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) else d
def _score(v): return max(0.0,min(100.0,_num(v,0)))
def _sym(v): return v.strip().upper() if isinstance(v,str) and v.strip() else "UNKNOWN"

def determine_cash_reserve_target(market_regime:str)->float:
    if market_regime in ["STRONG_BULL","BULL"]: return 0.20
    if market_regime in ["BEAR","STRONG_BEAR","HIGH_VOLATILITY"]: return 0.30
    return 0.25

def calculate_master_score(row:Mapping[str,Any])->float:
    if not isinstance(row,Mapping): raise ValueError("holding must be mapping")
    return round(sum(_score(row.get(k,0))*w/100 for k,w in MASTER_SCORE_WEIGHTS.items()),2)

def assign_rank(score:float)->str:
    if score>=90: return "A"
    if score>=80: return "B"
    if score>=70: return "C"
    if score>=60: return "D"
    if score>=50: return "E"
    return "F"

def detect_sale_signal(row:Mapping[str,Any])->bool:
    if bool(row.get("sale_signal",False)): return True
    if _score(row.get("opportunity_score",0)) < 50: return True
    if _score(row.get("momentum_score",0)) < 45: return True
    if _score(row.get("conviction_score",0)) <= max(0.0,_score(row.get("previous_conviction_score",0))-10): return True
    return False

def build_lifecycle_actions(holdings:Iterable[Mapping[str,Any]])->List[Dict[str,Any]]:
    actions=[]
    rows=[]
    for raw in holdings:
        row=dict(raw); row["symbol"]=_sym(row.get("symbol","UNKNOWN")); row["master_score"]=calculate_master_score(row); rows.append(row)
    rows.sort(key=lambda r:(-r["master_score"],r["symbol"]))
    for row in rows:
        prev=_score(row.get("previous_master_score",row["master_score"])); sale=detect_sale_signal(row); reasons=[]
        action="HOLD"
        if sale:
            action="EXIT_TO_SGOV"; reasons.append("Sale signal detected; stage capital in SGOV for re-entry or reassignment review.")
        elif row["master_score"]>=90:
            action="INCREASE"; reasons.append("A-ranked holding; eligible for additional cash if available.")
        else:
            reasons.append("No sale signal; holding remains allocated on merit.")
        actions.append(asdict(LifecycleAction(row["symbol"],assign_rank(prev),assign_rank(row["master_score"]),row["master_score"],_num(row.get("allocation_pct",0)),_num(row.get("allocation_dollars",0)),action,reasons,_num(row.get("expected_monthly_income",0)),_num(row.get("expected_annual_income",0)))))
    return actions

def build_portfolio_lifecycle_report(holdings:Iterable[Mapping[str,Any]]|None=None, portfolio_value:float=500.0, cash_balance:float=0.0, market_regime:str="UNKNOWN")->Dict[str,Any]:
    if portfolio_value<=0 or cash_balance<0: raise ValueError("portfolio_value must be positive and cash_balance non-negative")
    if market_regime not in SUPPORTED_REGIMES: market_regime="UNKNOWN"
    rows=list(holdings or []); actions=build_lifecycle_actions(rows); reserve_pct=determine_cash_reserve_target(market_regime); reserve=round(portfolio_value*reserve_pct,2); excess=round(max(0.0,cash_balance-reserve),2)
    monthly=round(sum(a["expected_monthly_income"] for a in actions),2); annual=round(sum(a["expected_annual_income"] for a in actions),2)
    allocated=round(sum(a["allocation_dollars"] for a in actions),2)
    warnings=[]
    if not rows: warnings.append("No holdings supplied; generated valid empty lifecycle report.")
    payload=asdict(PortfolioLifecycleReport(BOT_NAME,BOT_TYPE,MODULE_NAME,MODULE_VERSION,SCHEMA_VERSION,GENERATED_BY,_now(),True,False,False,True,market_regime,float(portfolio_value),float(cash_balance),reserve_pct,reserve,excess,len(rows),actions,len(actions),{"expected_monthly_income":monthly,"expected_annual_income":annual},{"allocated_dollars":allocated,"cash_balance":float(cash_balance),"available_excess_cash":excess},warnings,[],LIFECYCLE_RULES,SAFETY_GUARANTEES))
    validate_portfolio_lifecycle_report(payload)
    return payload

def validate_portfolio_lifecycle_report(payload:Any)->bool:
    if not isinstance(payload,Mapping): raise ValueError("payload must be mapping")
    for f in REPORT_REQUIRED_FIELDS:
        if f not in payload: raise ValueError(f"missing required field: {f}")
    for k,v in {"paper_trade_mode":True,"live_trading_enabled":False,"broker_execution_enabled":False,"reporting_only":True}.items():
        if payload[k] is not v: raise ValueError(f"{k} must be {v}")
    if payload["market_regime"] not in SUPPORTED_REGIMES: raise ValueError("unsupported market regime")
    for n in ["portfolio_value","cash_balance","cash_reserve_target_pct","cash_reserve_target_dollars","available_excess_cash"]:
        if not isinstance(payload[n],(int,float)) or isinstance(payload[n],bool) or payload[n]<0: raise ValueError(f"{n} must be non-negative number")
    for lf in ["lifecycle_actions","warnings","errors","lifecycle_rules","safety_guarantees"]:
        if not isinstance(payload[lf],list): raise ValueError(f"{lf} must be list")
    if payload["action_count"]!=len(payload["lifecycle_actions"]): raise ValueError("action_count mismatch")
    for a in payload["lifecycle_actions"]:
        for f in ACTION_FIELDS:
            if f not in a: raise ValueError(f"action missing {f}")
        if a["lifecycle_action"] not in SUPPORTED_ACTIONS: raise ValueError("unsupported lifecycle action")
        if a["previous_rank"] not in SUPPORTED_RANKS or a["current_rank"] not in SUPPORTED_RANKS: raise ValueError("unsupported rank")
        if not isinstance(a["reason"],list): raise ValueError("reason must be list")
    return True

def write_portfolio_lifecycle_report_json(path:str="portfolio_lifecycle_report.json")->Dict[str,Any]:
    p=build_portfolio_lifecycle_report(); Path(path).write_text(json.dumps(p,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return p

def read_portfolio_lifecycle_report_json(path:str="portfolio_lifecycle_report.json")->Dict[str,Any]:
    p=json.loads(Path(path).read_text(encoding="utf-8")); validate_portfolio_lifecycle_report(p); return p

def write_portfolio_lifecycle_report_csv(path:str="portfolio_lifecycle_report.csv")->Dict[str,Any]:
    p=build_portfolio_lifecycle_report()
    with Path(path).open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=ACTION_FIELDS); w.writeheader(); [w.writerow({f:a.get(f,"") for f in ACTION_FIELDS}) for a in p["lifecycle_actions"]]
    return p

def format_portfolio_lifecycle_report_markdown(payload:Mapping[str,Any])->str:
    validate_portfolio_lifecycle_report(payload)
    lines=["# Portfolio Lifecycle Report","",f"- Market Regime: {payload['market_regime']}",f"- Portfolio Value: ${payload['portfolio_value']:.2f}",f"- Cash Reserve Target: ${payload['cash_reserve_target_dollars']:.2f}",f"- Expected Monthly Income: ${payload['income_summary']['expected_monthly_income']:.2f}","","## Lifecycle Actions","","| Symbol | Rank | Score | Action | Allocation |","|---|---|---:|---|---:|"]
    for a in payload["lifecycle_actions"]: lines.append(f"| {a['symbol']} | {a['current_rank']} | {a['master_score']} | {a['lifecycle_action']} | {a['allocation_dollars']} |")
    lines += ["","## Lifecycle Rules"]+[f"- {x}" for x in payload["lifecycle_rules"]]+["","## Safety Guarantees"]+[f"- {x}" for x in payload["safety_guarantees"]]
    return "\n".join(lines)+"\n"

def write_portfolio_lifecycle_report_markdown(path:str="portfolio_lifecycle_report.md")->Dict[str,Any]:
    p=build_portfolio_lifecycle_report(); Path(path).write_text(format_portfolio_lifecycle_report_markdown(p),encoding="utf-8"); return p

if __name__=="__main__":
    write_portfolio_lifecycle_report_json(); write_portfolio_lifecycle_report_csv(); write_portfolio_lifecycle_report_markdown()
