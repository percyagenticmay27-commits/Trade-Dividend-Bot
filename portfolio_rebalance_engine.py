"""
Portfolio Rebalance Engine for the Dividend Bot.

Paper-only rebalance logic based on merit, sale signals, SGOV staging, re-entry
review, and minimum improvement thresholds. No holding is permanent or core.
"""
from __future__ import annotations

import csv, json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME="portfolio_rebalance_engine"
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
IMPROVEMENT_THRESHOLD=5.0
OPPORTUNITY_EXIT_THRESHOLD=50.0
CONVICTION_DROP_THRESHOLD=10.0
MOMENTUM_NEGATIVE_THRESHOLD=45.0

HOLD="HOLD"
REBALANCE_REVIEW="REBALANCE_REVIEW"
MOVE_TO_SGOV="MOVE_TO_SGOV"
REENTER_ORIGINAL="REENTER_ORIGINAL"
REALLOCATE_TO_BETTER_OPPORTUNITY="REALLOCATE_TO_BETTER_OPPORTUNITY"
REDISTRIBUTE_TO_PORTFOLIO="REDISTRIBUTE_TO_PORTFOLIO"
DEPLOY_EXCESS_CASH="DEPLOY_EXCESS_CASH"
SUPPORTED_ACTIONS=[HOLD,REBALANCE_REVIEW,MOVE_TO_SGOV,REENTER_ORIGINAL,REALLOCATE_TO_BETTER_OPPORTUNITY,REDISTRIBUTE_TO_PORTFOLIO,DEPLOY_EXCESS_CASH]
SUPPORTED_SALE_SIGNALS=["CONVICTION_DECREASE","MOMENTUM_NEGATIVE","OPPORTUNITY_BELOW_THRESHOLD","STRATEGY_EXIT"]
SUPPORTED_REGIMES=["STRONG_BULL","BULL","NEUTRAL","BEAR","STRONG_BEAR","HIGH_VOLATILITY","UNKNOWN"]
SAFETY_GUARANTEES=["paper_trade_mode is enforced as True","reporting_only is enforced as True","live_trading_enabled is enforced as False","broker_execution_enabled is enforced as False","no Robinhood execution is performed","no brokerage execution is performed","no order placement is performed","rebalance actions are recommendations only"]
INVESTMENT_CONSTITUTION=["No permanent core holdings.","Every stock, ETF, or pair competes on its own merit.","A higher score alone never causes a sale.","A valid sale signal is required before capital is released.","Released capital moves to SGOV while re-entry or replacement is evaluated.","Capital is assigned based on objective rank, not history or preference."]
MASTER_SCORE_WEIGHTS={"opportunity_score":30,"conviction_score":25,"momentum_score":20,"entry_score":10,"technical_score":10,"market_regime_support":5}
REPORT_REQUIRED_FIELDS=["bot_name","bot_type","module_name","module_version","schema_version","generated_by","generated_at_utc","paper_trade_mode","live_trading_enabled","broker_execution_enabled","reporting_only","rebalance_objective","improvement_threshold","cash_shield_symbol","market_regime","cash_reserve_target_pct","master_score_weights","holdings_reviewed","watchlist_reviewed","rebalance_actions","action_count","sale_signal_count","capital_movement_ledger","warnings","errors","investment_constitution","safety_guarantees"]
ACTION_FIELDS=["symbol","current_rank","new_rank","master_score","previous_master_score","sale_signals","recommended_action","destination_symbol","capital_to_stage_in_sgov","why","review_required"]

@dataclass(frozen=True)
class RebalanceCandidate:
    symbol:str
    opportunity_score:float=0.0
    conviction_score:float=0.0
    previous_conviction_score:float=0.0
    momentum_score:float=0.0
    entry_score:float=0.0
    technical_score:float=0.0
    market_regime_support:float=0.0
    previous_master_score:float=0.0
    current_allocation_dollars:float=0.0
    strategy_exit:bool=False
    is_current_holding:bool=True

@dataclass(frozen=True)
class RebalanceAction:
    symbol:str
    current_rank:str
    new_rank:str
    master_score:float
    previous_master_score:float
    sale_signals:List[str]
    recommended_action:str
    destination_symbol:str=""
    capital_to_stage_in_sgov:float=0.0
    why:List[str]=field(default_factory=list)
    review_required:bool=True

@dataclass(frozen=True)
class PortfolioRebalanceReport:
    bot_name:str; bot_type:str; module_name:str; module_version:str; schema_version:str; generated_by:str; generated_at_utc:str
    paper_trade_mode:bool; live_trading_enabled:bool; broker_execution_enabled:bool; reporting_only:bool
    rebalance_objective:str; improvement_threshold:float; cash_shield_symbol:str; market_regime:str; cash_reserve_target_pct:float
    master_score_weights:Dict[str,float]; holdings_reviewed:int; watchlist_reviewed:int; rebalance_actions:List[Dict[str,Any]]; action_count:int; sale_signal_count:int; capital_movement_ledger:List[Dict[str,Any]]; warnings:List[str]; errors:List[str]; investment_constitution:List[str]; safety_guarantees:List[str]

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def _num(v,d=0.0): return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) else d
def _score(v): return max(0.0,min(100.0,_num(v,0.0)))
def _sym(v): return v.strip().upper() if isinstance(v,str) and v.strip() else "UNKNOWN"

def determine_cash_reserve_target(market_regime:str)->float:
    if market_regime in ["STRONG_BULL","BULL"]: return 0.20
    if market_regime in ["BEAR","STRONG_BEAR","HIGH_VOLATILITY"]: return 0.30
    return 0.25

def calculate_master_score(candidate:Mapping[str,Any])->float:
    if not isinstance(candidate,Mapping): raise ValueError("candidate must be mapping")
    total=0.0
    for k,w in MASTER_SCORE_WEIGHTS.items(): total += _score(candidate.get(k,0))*w/100.0
    return round(total,2)

def assign_rank(score:float)->str:
    if score>=90: return "A"
    if score>=80: return "B"
    if score>=70: return "C"
    if score>=60: return "D"
    if score>=50: return "E"
    return "F"

def detect_sale_signals(candidate:Mapping[str,Any])->List[str]:
    signals=[]
    if _score(candidate.get("conviction_score",0)) <= max(0.0,_score(candidate.get("previous_conviction_score",0))-CONVICTION_DROP_THRESHOLD): signals.append("CONVICTION_DECREASE")
    if _score(candidate.get("momentum_score",0)) < MOMENTUM_NEGATIVE_THRESHOLD: signals.append("MOMENTUM_NEGATIVE")
    if _score(candidate.get("opportunity_score",0)) < OPPORTUNITY_EXIT_THRESHOLD: signals.append("OPPORTUNITY_BELOW_THRESHOLD")
    if bool(candidate.get("strategy_exit",False)): signals.append("STRATEGY_EXIT")
    return signals

def _best_watchlist(watchlist:Iterable[Mapping[str,Any]])->Dict[str,Any]|None:
    rows=[]
    for raw in watchlist:
        r=dict(raw); r["symbol"]=_sym(r.get("symbol","UNKNOWN")); r["master_score"]=calculate_master_score(r); rows.append(r)
    if not rows: return None
    rows.sort(key=lambda r:(-r["master_score"],r["symbol"]))
    return rows[0]

def _best_existing(holdings:Iterable[Mapping[str,Any]], exclude_symbol:str)->Dict[str,Any]|None:
    rows=[]
    for raw in holdings:
        r=dict(raw); r["symbol"]=_sym(r.get("symbol","UNKNOWN"));
        if r["symbol"]==exclude_symbol: continue
        r["master_score"]=calculate_master_score(r); rows.append(r)
    if not rows: return None
    rows.sort(key=lambda r:(-r["master_score"],r["symbol"]))
    return rows[0]

def build_rebalance_actions(holdings:Iterable[Mapping[str,Any]], watchlist:Iterable[Mapping[str,Any]]|None=None)->List[Dict[str,Any]]:
    holding_rows=[dict(h) for h in holdings]
    watchlist_rows=list(watchlist or [])
    actions=[]
    for raw in holding_rows:
        symbol=_sym(raw.get("symbol","UNKNOWN")); score=calculate_master_score(raw); previous=_score(raw.get("previous_master_score",score)); signals=detect_sale_signals(raw); why=[]
        action=HOLD; dest=""; staged=0.0
        if signals:
            action=MOVE_TO_SGOV; dest=CASH_SHIELD_SYMBOL; staged=max(0.0,_num(raw.get("current_allocation_dollars",0),0)); why.append("Sale signal detected; capital is staged in SGOV before reassignment.")
            best_new=_best_watchlist(watchlist_rows); best_existing=_best_existing(holding_rows,symbol)
            if best_new and best_new["master_score"] >= score + IMPROVEMENT_THRESHOLD:
                action=REALLOCATE_TO_BETTER_OPPORTUNITY; dest=best_new["symbol"]; why.append(f"Watchlist opportunity exceeds exited holding by at least {IMPROVEMENT_THRESHOLD} points.")
            elif best_existing and best_existing["master_score"] >= score + IMPROVEMENT_THRESHOLD:
                action=REDISTRIBUTE_TO_PORTFOLIO; dest=best_existing["symbol"]; why.append(f"Existing holding outranks exited holding by at least {IMPROVEMENT_THRESHOLD} points.")
            else:
                action=REENTER_ORIGINAL; dest=symbol; why.append("No better opportunity exceeded threshold; original holding remains re-entry candidate.")
        else:
            why.append("No sale signal; holding remains allocated regardless of outside opportunity scores.")
        actions.append(asdict(RebalanceAction(symbol=symbol,current_rank=assign_rank(previous),new_rank=assign_rank(score),master_score=score,previous_master_score=previous,sale_signals=signals,recommended_action=action,destination_symbol=dest,capital_to_stage_in_sgov=round(staged,2),why=why,review_required=True)))
    actions.sort(key=lambda r:(r["recommended_action"]==HOLD, -r["master_score"], r["symbol"]))
    return actions

def build_capital_movement_ledger(actions:Iterable[Mapping[str,Any]])->List[Dict[str,Any]]:
    ledger=[]
    for a in actions:
        if a.get("recommended_action")!=HOLD:
            ledger.append({"source_symbol":a["symbol"],"stage_symbol":CASH_SHIELD_SYMBOL,"destination_symbol":a.get("destination_symbol",""),"amount":a.get("capital_to_stage_in_sgov",0.0),"reason":"; ".join(a.get("why",[]))})
    return ledger

def build_portfolio_rebalance_report(holdings:Iterable[Mapping[str,Any]]|None=None, watchlist:Iterable[Mapping[str,Any]]|None=None, market_regime:str="UNKNOWN")->Dict[str,Any]:
    if market_regime not in SUPPORTED_REGIMES: market_regime="UNKNOWN"
    holdings_list=list(holdings or []); watchlist_list=list(watchlist or [])
    actions=build_rebalance_actions(holdings_list,watchlist_list)
    warnings=[]
    if not holdings_list: warnings.append("No holdings supplied; generated valid empty rebalance report.")
    payload=asdict(PortfolioRebalanceReport(BOT_NAME,BOT_TYPE,MODULE_NAME,MODULE_VERSION,SCHEMA_VERSION,GENERATED_BY,_now(),True,False,False,True,"BALANCED_INCOME_AND_GROWTH",IMPROVEMENT_THRESHOLD,CASH_SHIELD_SYMBOL,market_regime,determine_cash_reserve_target(market_regime),MASTER_SCORE_WEIGHTS,len(holdings_list),len(watchlist_list),actions,len(actions),sum(1 for a in actions if a["sale_signals"]),build_capital_movement_ledger(actions),warnings,[],INVESTMENT_CONSTITUTION,SAFETY_GUARANTEES))
    validate_portfolio_rebalance_report(payload)
    return payload

def validate_portfolio_rebalance_report(payload:Any)->bool:
    if not isinstance(payload,Mapping): raise ValueError("payload must be mapping")
    for f in REPORT_REQUIRED_FIELDS:
        if f not in payload: raise ValueError(f"missing required field: {f}")
    for k,v in {"paper_trade_mode":True,"live_trading_enabled":False,"broker_execution_enabled":False,"reporting_only":True}.items():
        if payload[k] is not v: raise ValueError(f"{k} must be {v}")
    if payload["cash_shield_symbol"]!=CASH_SHIELD_SYMBOL: raise ValueError("cash_shield_symbol must be SGOV")
    if payload["market_regime"] not in SUPPORTED_REGIMES: raise ValueError("unsupported market regime")
    if payload["master_score_weights"]!=MASTER_SCORE_WEIGHTS: raise ValueError("master_score_weights must match approved weights")
    for lf in ["rebalance_actions","capital_movement_ledger","warnings","errors","investment_constitution","safety_guarantees"]:
        if not isinstance(payload[lf],list): raise ValueError(f"{lf} must be list")
    if payload["action_count"]!=len(payload["rebalance_actions"]): raise ValueError("action_count mismatch")
    if payload["sale_signal_count"]!=sum(1 for a in payload["rebalance_actions"] if a.get("sale_signals")): raise ValueError("sale_signal_count mismatch")
    for a in payload["rebalance_actions"]:
        for f in ACTION_FIELDS:
            if f not in a: raise ValueError(f"action missing {f}")
        if a["recommended_action"] not in SUPPORTED_ACTIONS: raise ValueError("unsupported action")
        if not isinstance(a["sale_signals"],list): raise ValueError("sale_signals must be list")
        for s in a["sale_signals"]:
            if s not in SUPPORTED_SALE_SIGNALS: raise ValueError("unsupported sale signal")
    return True

def write_portfolio_rebalance_report_json(path:str="portfolio_rebalance_report.json")->Dict[str,Any]:
    p=build_portfolio_rebalance_report(); Path(path).write_text(json.dumps(p,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return p

def read_portfolio_rebalance_report_json(path:str="portfolio_rebalance_report.json")->Dict[str,Any]:
    p=json.loads(Path(path).read_text(encoding="utf-8")); validate_portfolio_rebalance_report(p); return p

def write_portfolio_rebalance_report_csv(path:str="portfolio_rebalance_report.csv")->Dict[str,Any]:
    p=build_portfolio_rebalance_report()
    with Path(path).open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=ACTION_FIELDS); w.writeheader(); [w.writerow({f:a.get(f,"") for f in ACTION_FIELDS}) for a in p["rebalance_actions"]]
    return p

def format_portfolio_rebalance_report_markdown(payload:Mapping[str,Any])->str:
    validate_portfolio_rebalance_report(payload)
    lines=["# Portfolio Rebalance Report","",f"- Objective: {payload['rebalance_objective']}",f"- Market Regime: {payload['market_regime']}",f"- Cash Reserve Target: {payload['cash_reserve_target_pct']}",f"- Action Count: {payload['action_count']}","","## Rebalance Actions","","| Symbol | Rank | Score | Sale Signals | Action | Destination |","|---|---|---:|---|---|---|"]
    for a in payload["rebalance_actions"]: lines.append(f"| {a['symbol']} | {a['new_rank']} | {a['master_score']} | {', '.join(a['sale_signals']) or 'None'} | {a['recommended_action']} | {a['destination_symbol']} |")
    lines += ["","## Investment Constitution"]+[f"- {x}" for x in payload["investment_constitution"]]+["","## Safety Guarantees"]+[f"- {x}" for x in payload["safety_guarantees"]]
    return "\n".join(lines)+"\n"

def write_portfolio_rebalance_report_markdown(path:str="portfolio_rebalance_report.md")->Dict[str,Any]:
    p=build_portfolio_rebalance_report(); Path(path).write_text(format_portfolio_rebalance_report_markdown(p),encoding="utf-8"); return p

if __name__=="__main__":
    write_portfolio_rebalance_report_json(); write_portfolio_rebalance_report_csv(); write_portfolio_rebalance_report_markdown()
