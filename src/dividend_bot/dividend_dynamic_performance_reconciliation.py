"""Reporting-only dynamic sleeve round trips and SGOV receipt reconciliation.

The independently persisted transaction journal (not historical legacy CSV) is
identity-matched to SGOV funding receipts. Cash proceeds are not profits.
"""
from __future__ import annotations
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

CENT=Decimal('0.01')

def _amount(value: Any)->Decimal:
    try:
        x=Decimal(str(value))
        if not x.is_finite() or x<0:raise ValueError('INVALID_NONNEGATIVE_AMOUNT')
        return x
    except (TypeError,InvalidOperation) as exc:raise ValueError('INVALID_NONNEGATIVE_AMOUNT') from exc

def _cent(value: Decimal)->Decimal:
    return value.quantize(CENT,rounding=ROUND_HALF_UP)

def _outcome(pnl:Decimal)->str:
    return 'WIN' if pnl>0 else 'LOSS' if pnl<0 else 'FLAT'

def reconcile_dynamic_trades(transactions:list[Mapping[str,Any]],ownership:Mapping[str,Any]|None,
                             sleeves:Mapping[str,Any]|None)->dict[str,Any]:
    receipts=(ownership or {}).get('funded_exit_receipts',{})
    if not isinstance(receipts,dict):raise ValueError('SGOV_FUNDING_RECEIPTS_INVALID')
    source_ids=set()
    open_legs={}
    completed=[];warn=[];excluded=[]
    receipt_matches=set();funded_expected=Decimal(0);funded_recorded=Decimal(0)
    income_by_key=defaultdict(lambda:Decimal(0))
    for row in transactions:
        if not isinstance(row,Mapping):raise ValueError('INVALID_DYNAMIC_EVENT')
        action=row.get('action')
        if action not in ('PAPER_BUY_OPEN','PAPER_SELL_TO_SGOV','PAPER_DIVIDEND_REINVESTED','PAPER_DIVIDEND_PARKED'):
            continue
        txid=str(row.get('transaction_id') or '').strip()
        if not txid or txid in source_ids:
            raise ValueError('MISSING_OR_DUPLICATE_DYNAMIC_TRANSACTION_ID:'+txid)
        source_ids.add(txid)
        if row.get('paper_trade_mode') is not True:raise ValueError('DYNAMIC_EVENT_NOT_PAPER_ONLY')
        pair=str(row.get('pair_id') or '').strip();sleeve_id=str(row.get('sleeve_id') or '').strip()
        if not pair or not sleeve_id:raise ValueError('DYNAMIC_EVENT_IDENTITY_MISSING')
        if action=='PAPER_BUY_OPEN':
            for role in ('income','growth'):
                key=(sleeve_id,role)
                if key in open_legs:
                    old=open_legs[key]
                    warn.append('UNMATCHED_DUPLICATE_BUY_REPLACED:'+str(old['entry_transaction_id']))
                    excluded.append({'reason':'DUPLICATE_OPEN_WITHOUT_EXIT','entry_transaction_id':old['entry_transaction_id'],
                                     'pair':pair,'symbol':old['symbol']})
                open_legs[key]={'pair':pair,'sleeve_id':sleeve_id,'role':role,
                     'symbol':str(row.get(role+'_symbol') or '').strip().upper(),
                     'entry_transaction_id':txid,'entry_date':row.get('created_at_utc'),
                     'entry_value':_amount(row[role+'_allocated_cash']),
                     'dividend_reinvested':Decimal(0),'dividend_parked':Decimal(0),
                     'source':'state/dividend_dynamic_sleeve_transactions.jsonl'}
            continue
        role=str(row.get('leg_role') or '').lower()
        if role not in ('income','growth'):raise ValueError('INVALID_DYNAMIC_LEG_ROLE')
        key=(sleeve_id,role)
        if action in ('PAPER_DIVIDEND_REINVESTED','PAPER_DIVIDEND_PARKED'):
            if key in open_legs:
                field='dividend_reinvested' if action=='PAPER_DIVIDEND_REINVESTED' else 'dividend_parked'
                open_legs[key][field]+=_amount(row.get('cash'))
            continue
        proceeds=_amount(row.get('proceeds'))
        if key not in open_legs:
            warn.append('UNMATCHED_DYNAMIC_EXIT:'+txid)
            excluded.append({'reason':'EXIT_WITHOUT_MATCHED_ENTRY','transaction_id':txid,
                             'pair':pair,'symbol':row.get('symbol'),'proceeds':str(_cent(proceeds))})
            continue
        entry=open_legs.pop(key)
        symbol=str(row.get('symbol') or '').strip().upper()
        if symbol!=entry['symbol'] or pair!=entry['pair']:
            raise ValueError('DYNAMIC_BUY_EXIT_SYMBOL_OR_PAIR_MISMATCH:'+txid)
        # Reinvested dividends are already reflected in the final shares and
        # the proceeds, so do not add them to realized total-return P/L again.
        # Parked distributions remain separate SGOV cash, not exit proceeds.
        pnl=proceeds-entry['entry_value']
        income=entry['dividend_reinvested']+entry['dividend_parked']
        recorded=receipts.get(txid)
        receipt_status='FUNDED_EXIT_RECEIPT_CONFIRMED' if recorded is not None else 'HISTORICAL_NO_FUNDED_EXIT_RECEIPT'
        if recorded is not None:
            if not isinstance(recorded,Mapping) or recorded.get('sleeve_id')!=sleeve_id:
                raise ValueError('SGOV_RECEIPT_IDENTITY_MISMATCH:'+txid)
            actual=_amount(recorded.get('amount'))
            if _cent(actual)!=_cent(proceeds):raise ValueError('SGOV_RECEIPT_PROCEEDS_MISMATCH:'+txid)
            funded_expected+=_cent(proceeds);funded_recorded+=_cent(actual)
            receipt_matches.add(txid)
        base=entry['entry_value']
        completed.append({'pair':pair,'sleeve':'A' if role=='income' else 'B','symbol':symbol,
           'sleeve_id':sleeve_id,'entry_transaction_id':entry['entry_transaction_id'],
           'exit_transaction_id':txid,'entry_date':entry['entry_date'],
           'exit_date':row.get('created_at_utc'),'entry_value':float(_cent(base)),
           'exit_value':float(_cent(proceeds)),'realized_value':float(_cent(proceeds)),
           'pnl':float(_cent(pnl)),'total_return_pct':round(float((pnl/base)*100) if base else 0,4),
           'outcome':_outcome(pnl),'income_received':float(_cent(income)),
           'reinvested_income_in_exit_proceeds':float(_cent(entry['dividend_reinvested'])),
           'separately_parked_dividend_cash':float(_cent(entry['dividend_parked'])),
           'sgov_receipt_status':receipt_status,
           'sgov_receipt_amount':float(_cent(_amount(recorded['amount']))) if recorded else None,
           'sgov_receipt_id':txid if recorded else None,
           'source':entry['source'],'paper_trade_mode':True})
    missing=sorted(set(receipts)-receipt_matches)
    if missing:raise ValueError('SGOV_RECEIPTS_WITHOUT_MATCHED_DYNAMIC_EXIT:'+','.join(missing))
    # Check current live shares, but preserve incomplete journal exposure as
    # a warning rather than fabricating a sale.
    current={s.get('sleeve_id'):s for s in (sleeves or {}).get('sleeves',[]) if isinstance(s,Mapping)}
    current_opens=[]
    for (_,role),item in open_legs.items():
        s=current.get(item['sleeve_id'])
        shares=float(s.get(role+'_shares',0)) if s else None
        if s is not None and shares<=1e-12:
            warn.append('UNMATCHED_DYNAMIC_OPEN_WITH_ZERO_CURRENT_SHARES:'+item['entry_transaction_id'])
        current_opens.append({'pair':item['pair'],'sleeve':'A' if role=='income' else 'B',
                              'symbol':item['symbol'],'entry_transaction_id':item['entry_transaction_id'],
                              'entry_value':float(_cent(item['entry_value'])),'current_shares':shares,
                              'source':item['source']})
    total_proceeds=sum((_cent(_amount(t['exit_value'])) for t in completed),Decimal(0))
    funded=[t for t in completed if t['sgov_receipt_id']]
    return {'closed_trades':completed,'journal_closed_trade_count':len(completed),
        'journal_realized_pnl':float(_cent(sum((_amount(abs(t['pnl']))*(1 if t['pnl']>=0 else -1) for t in completed),Decimal(0)))),
        'journal_gross_exit_proceeds':float(_cent(total_proceeds)),
        'sgov_receipt_confirmed_count':len(funded),'sgov_receipt_confirmed_proceeds':float(_cent(funded_expected)),
        'sgov_receipt_recorded_proceeds':float(_cent(funded_recorded)),
        'sgov_receipt_reconciliation_difference':float(_cent(funded_expected-funded_recorded)),
        'historical_exits_without_funded_receipt':len(completed)-len(funded),
        'unmatched_open_positions':current_opens,'excluded_ambiguous_events':excluded,'warnings':warn,
        'sgov_reconciliation_status':'ALL_AVAILABLE_FUNDED_RECEIPTS_MATCHED' if not missing and funded_expected==funded_recorded else 'RECONCILIATION_MISMATCH',
        'source':'state/dividend_dynamic_sleeve_transactions.jsonl',
        'receipt_source':'state/dividend_sgov_ownership.json#funded_exit_receipts',
        'paper_only':True,'reporting_only':True}
