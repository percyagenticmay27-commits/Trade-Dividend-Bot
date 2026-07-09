"""
Income Reinvestment Engine for the Dividend Bot.

Allocates received distributions according to self-funding rules:
- single holding distributions reinvest into themselves
- ETF pair distributions split 50/50 between income and growth symbols
- SGOV reserve target is protected
- exceptional opportunities may receive limited excess cash deployment

All outputs are paper-only recommendations. No orders are placed.
"""
from __future__ import annotations

import csv, json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME="income_reinvestment_engine"
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
EXCEPTIONAL_OPPORTUNITY_SCORE=90.0
MAX_EXCESS_CASH_DEPLOYMENT_PCT=0.10

SELF_REINVEST="SELF_REINVEST"
SPLIT_PAIR_50_50="SPLIT_PAIR_50_50"
PROTECT_CASH_RESERVE="PROTECT_CASH_RESERVE"
DEPLOY_EXCESS_CASH="DEPLOY_EXCESS_CASH"
HOLD_CASH="HOLD_CASH"
SUPPORTED_REINVESTMENT_ACTIONS=[SELF_REINVEST,SPLIT_PAIR_50_50,PROTECT_CASH_RESERVE,DEPLOY_EXCESS_CASH,HOLD_CASH]
SUPPORTED_HOLDING_TYPES=["SINGLE","ETF_PAIR","CASH_SHIELD","UNKNOWN"]
SUPPORTED_REGIMES=["STRONG_BULL","BULL","NEUTRAL","BEAR","STRONG_BEAR","HIGH_VOLATILITY","UNKNOWN"]
SAFETY_GUARANTEES=["paper_trade_mode is enforced as True","reporting_only is enforced as True","live_trading_enabled is enforced as False","broker_execution_enabled is enforced as False","no Robinhood execution is performed","no brokerage execution is performed","no order placement is performed","income allocations are recommendations only"]
REINVESTMENT_RULES=["Single holding distributions reinvest into the same symbol.","ETF pair distributions split 50/50 between income_symbol and growth_symbol.","Cash reserve target is protected before excess cash is deployed.","Exceptional opportunities may receive up to 10% of excess cash above the reserve target."]
LEDGER_FIELDS=["source_symbol","holding_type","distribution_amount","action","destination_symbol","destination_amount","reserve_protected","why"]
REPORT_REQUIRED_FIELDS=["bot_name","bot_type","module_name","module_version","schema_version","generated_by","generated_at_utc","paper_trade_mode","live_trading_enabled","broker_execution_enabled","reporting_only","portfolio_value","cash_balance","cash_reserve_target_pct","cash_reserve_target_dollars","excess_cash","total_distributions_received","total_reinvested","total_cash_held","reinvestment_actions","action_count","reinvestment_ledger","warnings","errors","reinvestment_rules","safety_guarantees"]

@dataclass(frozen=True)
class DistributionEvent:
    source_symbol:str
    distribution_amount:float
    holding_type:str="SINGLE"
    income_symbol:str=""
    growth_symbol:str=""

@dataclass(frozen=True)
class ReinvestmentAction:
    source_symbol:str
    holding_type:str
    distribution_amount:float
    action:str
    destination_symbol:str
    destination_amount:float
    reserve_protected:bool=True
    why:List[str]=field(default_factory=list)

@dataclass(frozen=True)
class IncomeReinvestmentReport:
    bot_name:str; bot_type:str; module_name:str; module_version:str; schema_version:str; generated_by:str; generated_at_utc:str
    paper_trade_mode:bool; live_trading_enabled:bool; broker_execution_enabled:bool; reporting_only:bool
    portfolio_value:float; cash_balance:float; cash_reserve_target_pct:float; cash_reserve_target_dollars:float; excess_cash:float
    total_distributions_received:float; total_reinvested:float; total_cash_held:float
    reinvestment_actions:List[Dict[str,Any]]; action_count:int; reinvestment_ledger:List[Dict[str,Any]]; warnings:List[str]; errors:List[str]; reinvestment_rules:List[str]; safety_guarantees:List[str]

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def _num(v,d=0.0): return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) else d
def _sym(v): return v.strip().upper() if isinstance(v,str) and v.strip() else "UNKNOWN"

def determine_cash_reserve_target(market_regime:str)->float:
    if market_regime in ["STRONG_BULL","BULL"]: return 0.20
    if market_regime in ["BEAR","STRONG_BEAR","HIGH_VOLATILITY"]: return 0.30
    return 0.25

def normalize_distribution(event:Mapping[str,Any])->Dict[str,Any]:
    if not isinstance(event,Mapping): raise ValueError("distribution event must be mapping")
    holding_type=event.get("holding_type","SINGLE")
    if holding_type not in SUPPORTED_HOLDING_TYPES: holding_type="UNKNOWN"
    return {"source_symbol":_sym(event.get("source_symbol","UNKNOWN")),"distribution_amount":max(0.0,_num(event.get("distribution_amount",0))),"holding_type":holding_type,"income_symbol":_sym(event.get("income_symbol",event.get("source_symbol","UNKNOWN"))),"growth_symbol":_sym(event.get("growth_symbol","")) if event.get("growth_symbol","") else ""}

def build_reinvestment_actions(distributions:Iterable[Mapping[str,Any]], portfolio_value:float=500.0, cash_balance:float=0.0, market_regime:str="UNKNOWN", opportunities:Iterable[Mapping[str,Any]]|None=None)->List[Dict[str,Any]]:
    target_pct=determine_cash_reserve_target(market_regime)
    reserve_target=portfolio_value*target_pct
    reserve_protected=cash_balance>=reserve_target
    actions=[]
    for raw in distributions:
        event=normalize_distribution(raw)
        amount=event["distribution_amount"]
        if amount<=0:
            actions.append(asdict(ReinvestmentAction(event["source_symbol"],event["holding_type"],amount,HOLD_CASH,CASH_SHIELD_SYMBOL,0.0,reserve_protected,["Zero distribution amount; no reinvestment recommended."])))
            continue
        if not reserve_protected:
            actions.append(asdict(ReinvestmentAction(event["source_symbol"],event["holding_type"],amount,PROTECT_CASH_RESERVE,CASH_SHIELD_SYMBOL,round(amount,2),False,["Cash reserve is below target; distribution is directed to SGOV reserve."])))
        elif event["holding_type"]=="ETF_PAIR":
            half=round(amount/2.0,2)
            other=round(amount-half,2)
            actions.append(asdict(ReinvestmentAction(event["source_symbol"],"ETF_PAIR",amount,SPLIT_PAIR_50_50,event["income_symbol"],half,True,["ETF pair rule: 50% to income side."])))
            actions.append(asdict(ReinvestmentAction(event["source_symbol"],"ETF_PAIR",amount,SPLIT_PAIR_50_50,event["growth_symbol"],other,True,["ETF pair rule: 50% to growth side."])))
        elif event["holding_type"]=="CASH_SHIELD":
            actions.append(asdict(ReinvestmentAction(event["source_symbol"],"CASH_SHIELD",amount,HOLD_CASH,CASH_SHIELD_SYMBOL,round(amount,2),True,["Cash shield distribution remains in reserve."])))
        else:
            actions.append(asdict(ReinvestmentAction(event["source_symbol"],event["holding_type"],amount,SELF_REINVEST,event["source_symbol"],round(amount,2),True,["Single holding rule: distribution reinvests into itself."])))
    excess_cash=max(0.0,cash_balance-reserve_target)
    best=None
    for raw in list(opportunities or []):
        if not isinstance(raw,Mapping): continue
        score=_num(raw.get("allocation_score",raw.get("master_score",raw.get("opportunity_score",0))),0)
        if score>=EXCEPTIONAL_OPPORTUNITY_SCORE and (best is None or score>best["score"]): best={"symbol":_sym(raw.get("symbol","UNKNOWN")),"score":score}
    if best and excess_cash>0:
        deploy=round(excess_cash*MAX_EXCESS_CASH_DEPLOYMENT_PCT,2)
        if deploy>0:
            actions.append(asdict(ReinvestmentAction(CASH_SHIELD_SYMBOL,"CASH_SHIELD",deploy,DEPLOY_EXCESS_CASH,best["symbol"],deploy,True,["Exceptional opportunity found; deploying up to 10% of excess cash above reserve."])))
    return actions

def build_reinvestment_ledger(actions:Iterable[Mapping[str,Any]])->List[Dict[str,Any]]:
    ledger=[]
    for a in actions:
        ledger.append({"source_symbol":a["source_symbol"],"holding_type":a["holding_type"],"distribution_amount":a["distribution_amount"],"action":a["action"],"destination_symbol":a["destination_symbol"],"destination_amount":a["destination_amount"],"reserve_protected":a["reserve_protected"],"why":"; ".join(a.get("why",[]))})
    return ledger

def build_income_reinvestment_report(distributions:Iterable[Mapping[str,Any]]|None=None, portfolio_value:float=500.0, cash_balance:float=0.0, market_regime:str="UNKNOWN", opportunities:Iterable[Mapping[str,Any]]|None=None)->Dict[str,Any]:
    if portfolio_value<=0 or cash_balance<0: raise ValueError("portfolio_value must be positive and cash_balance non-negative")
    if market_regime not in SUPPORTED_REGIMES: market_regime="UNKNOWN"
    target_pct=determine_cash_reserve_target(market_regime); reserve=round(portfolio_value*target_pct,2); excess=round(max(0.0,cash_balance-reserve),2)
    events=list(distributions or [])
    actions=build_reinvestment_actions(events,portfolio_value,cash_balance,market_regime,opportunities)
    ledger=build_reinvestment_ledger(actions)
    total_received=round(sum(normalize_distribution(e)["distribution_amount"] for e in events),2)
    total_reinvested=round(sum(a["destination_amount"] for a in actions if a["action"] in [SELF_REINVEST,SPLIT_PAIR_50_50,DEPLOY_EXCESS_CASH]),2)
    total_cash_held=round(sum(a["destination_amount"] for a in actions if a["action"] in [PROTECT_CASH_RESERVE,HOLD_CASH]),2)
    warnings=[]
    if not events: warnings.append("No distribution events supplied; generated valid empty income reinvestment report.")
    payload=asdict(IncomeReinvestmentReport(BOT_NAME,BOT_TYPE,MODULE_NAME,MODULE_VERSION,SCHEMA_VERSION,GENERATED_BY,_now(),True,False,False,True,float(portfolio_value),float(cash_balance),target_pct,reserve,excess,total_received,total_reinvested,total_cash_held,actions,len(actions),ledger,warnings,[],REINVESTMENT_RULES,SAFETY_GUARANTEES))
    validate_income_reinvestment_report(payload)
    return payload

def validate_income_reinvestment_report(payload:Any)->bool:
    if not isinstance(payload,Mapping): raise ValueError("payload must be mapping")
    for f in REPORT_REQUIRED_FIELDS:
        if f not in payload: raise ValueError(f"missing required field: {f}")
    for k,v in {"paper_trade_mode":True,"live_trading_enabled":False,"broker_execution_enabled":False,"reporting_only":True}.items():
        if payload[k] is not v: raise ValueError(f"{k} must be {v}")
    for n in ["portfolio_value","cash_balance","cash_reserve_target_pct","cash_reserve_target_dollars","excess_cash","total_distributions_received","total_reinvested","total_cash_held"]:
        if not isinstance(payload[n],(int,float)) or isinstance(payload[n],bool) or payload[n]<0: raise ValueError(f"{n} must be non-negative number")
    for lf in ["reinvestment_actions","reinvestment_ledger","warnings","errors","reinvestment_rules","safety_guarantees"]:
        if not isinstance(payload[lf],list): raise ValueError(f"{lf} must be list")
    if payload["action_count"]!=len(payload["reinvestment_actions"]): raise ValueError("action_count mismatch")
    for a in payload["reinvestment_actions"]:
        if a["action"] not in SUPPORTED_REINVESTMENT_ACTIONS: raise ValueError("unsupported reinvestment action")
        if a["holding_type"] not in SUPPORTED_HOLDING_TYPES: raise ValueError("unsupported holding type")
        if not isinstance(a["why"],list): raise ValueError("why must be list")
    return True

def write_income_reinvestment_report_json(path:str="income_reinvestment_report.json")->Dict[str,Any]:
    p=build_income_reinvestment_report(); Path(path).write_text(json.dumps(p,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return p

def read_income_reinvestment_report_json(path:str="income_reinvestment_report.json")->Dict[str,Any]:
    p=json.loads(Path(path).read_text(encoding="utf-8")); validate_income_reinvestment_report(p); return p

def write_income_reinvestment_report_csv(path:str="income_reinvestment_report.csv")->Dict[str,Any]:
    p=build_income_reinvestment_report()
    with Path(path).open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=LEDGER_FIELDS); w.writeheader(); [w.writerow({f:r.get(f,"") for f in LEDGER_FIELDS}) for r in p["reinvestment_ledger"]]
    return p

def format_income_reinvestment_report_markdown(payload:Mapping[str,Any])->str:
    validate_income_reinvestment_report(payload)
    lines=["# Income Reinvestment Report","",f"- Portfolio Value: ${payload['portfolio_value']:.2f}",f"- Cash Reserve Target: ${payload['cash_reserve_target_dollars']:.2f}",f"- Excess Cash: ${payload['excess_cash']:.2f}",f"- Total Distributions Received: ${payload['total_distributions_received']:.2f}","","## Reinvestment Actions","","| Source | Action | Destination | Amount |","|---|---|---|---:|"]
    for a in payload["reinvestment_actions"]: lines.append(f"| {a['source_symbol']} | {a['action']} | {a['destination_symbol']} | {a['destination_amount']} |")
    lines += ["","## Reinvestment Rules"]+[f"- {x}" for x in payload["reinvestment_rules"]]+["","## Safety Guarantees"]+[f"- {x}" for x in payload["safety_guarantees"]]
    return "\n".join(lines)+"\n"

def write_income_reinvestment_report_markdown(path:str="income_reinvestment_report.md")->Dict[str,Any]:
    p=build_income_reinvestment_report(); Path(path).write_text(format_income_reinvestment_report_markdown(p),encoding="utf-8"); return p

if __name__=="__main__":
    write_income_reinvestment_report_json(); write_income_reinvestment_report_csv(); write_income_reinvestment_report_markdown()
