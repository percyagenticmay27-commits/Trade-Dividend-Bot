"""The dynamic journal is accounting evidence, never a new SGOV credit."""
import json
from pathlib import Path
import pytest
from src.dividend_bot.dividend_dynamic_performance_reconciliation import reconcile_dynamic_trades
from src.dividend_bot.dividend_paper_trade_performance import write_dividend_paper_trade_performance

SLEEVE='DIVIDEND-001:AAA:BBB'
def buy(tid='BUY1',amount=100):
 return {'action':'PAPER_BUY_OPEN','transaction_id':tid,'created_at_utc':'2026-11-10T14:00:00Z',
         'pair_id':'AAA / BBB','sleeve_id':SLEEVE,'paper_trade_mode':True,
         'income_symbol':'AAA','growth_symbol':'BBB','income_allocated_cash':amount,
         'growth_allocated_cash':50}
def event(action,tid,role='INCOME',**other):
 return {'action':action,'transaction_id':tid,'created_at_utc':'2026-11-17T15:16:00Z',
         'pair_id':'AAA / BBB','sleeve_id':SLEEVE,'leg_role':role,'paper_trade_mode':True,**other}
def ownership(proceeds='110.00'):
 return {'funded_exit_receipts':{'SALE1':{'amount':float(proceeds),'sleeve_id':SLEEVE}},
         'unassigned_reserve':10,'memberships':[{'symbol':'AAA','current_allocated_cash':110}],
         'reserve_reconciliation':{'principal':120,'valuation_adjustment':0.2}}
def rows():
 return [buy(),event('PAPER_DIVIDEND_REINVESTED','DIV1',cash=3.25),
         event('PAPER_SELL_TO_SGOV','SALE1',symbol='AAA',proceeds=110.0)]

def test_dynamic_exits_counted_once_and_cash_receipts_not_treated_as_pnl():
 out=reconcile_dynamic_trades(rows(),ownership(),None)
 trade=out['closed_trades'][0]
 assert trade['pnl']==10.00
 assert trade['exit_value']==110.00
 assert trade['reinvested_income_in_exit_proceeds']==3.25
 assert trade['income_received']==3.25
 assert out['sgov_receipt_confirmed_proceeds']==110
 assert out['sgov_receipt_reconciliation_difference']==0
 assert out['historical_exits_without_funded_receipt']==0
 assert out['journal_realized_pnl']==10
 assert out['unmatched_open_positions'][0]['symbol']=='BBB'

def test_receipt_identity_mismatch_fails_closed():
 with pytest.raises(ValueError,match='SGOV_RECEIPT_PROCEEDS_MISMATCH'):
  reconcile_dynamic_trades(rows(),ownership('109.50'),None)
 with pytest.raises(ValueError,match='SGOV_RECEIPTS_WITHOUT_MATCHED_DYNAMIC_EXIT'):
  reconcile_dynamic_trades([buy()],ownership(),None)

def test_historical_sale_without_new_funding_receipt_is_visible_not_fake_cash():
 out=reconcile_dynamic_trades(rows(),{'funded_exit_receipts':{}},None)
 assert out['journal_closed_trade_count']==1
 assert out['historical_exits_without_funded_receipt']==1
 assert out['sgov_receipt_confirmed_proceeds']==0
 assert out['closed_trades'][0]['sgov_receipt_status']=='HISTORICAL_NO_FUNDED_EXIT_RECEIPT'

def test_duplicate_buy_does_not_count_two_round_trips():
 out=reconcile_dynamic_trades([buy('OLD'),buy('NEW'),*rows()[1:]],ownership(),None)
 assert len(out['closed_trades'])==1
 assert out['closed_trades'][0]['entry_transaction_id']=='NEW'
 assert out['excluded_ambiguous_events'][0]['entry_transaction_id']=='OLD'

def test_writer_joins_legacy_and_new_dynamic_and_publishes_reconciled_sgov(tmp_path:Path):
 (tmp_path/'state').mkdir()
 (tmp_path/'paper_trade_log.csv').write_text('Date,Pair,Sleeve,Action,Ticker,Paper_Value\n'
   '2026-07-01,CCC / DDD,A,PAPER_BUY_OPEN,CCC,100\n'
   '2026-08-01,CCC / DDD,A,PAPER_SELL_TO_SGOV,CCC,90\n')
 (tmp_path/'state/dividend_dynamic_sleeve_transactions.jsonl').write_text(
    ''.join(json.dumps(x)+'\n' for x in rows()))
 (tmp_path/'state/dividend_sgov_ownership.json').write_text(json.dumps(ownership()))
 first=write_dividend_paper_trade_performance(tmp_path)
 data=json.loads(first.read_text())
 assert data['closed_trade_count']==2
 assert data['legacy_closed_trade_count']==1
 assert data['dynamic_closed_trade_count']==1
 assert data['legacy_realized_pnl']==-10
 assert data['dynamic_realized_pnl']==10
 assert data['realized_pnl']==0
 assert data['sgov_reconciliation']['current_sgov_principal_difference']==0
 assert data['sgov_reconciliation']['sgov_receipt_confirmed_proceeds']==110
 assert data['open_trade_count']==0 # no current dynamic registry provided; legacy closes only
 second=json.loads(write_dividend_paper_trade_performance(tmp_path).read_text())
 assert second['realized_pnl']==data['realized_pnl']
 assert second['closed_trade_count']==2

def test_writer_refuses_wrong_current_sgov_balance_and_keeps_previous_report(tmp_path:Path):
 (tmp_path/'state').mkdir()
 (tmp_path/'state/dividend_dynamic_sleeve_transactions.jsonl').write_text(
    ''.join(json.dumps(x)+'\n' for x in rows()))
 wrong=ownership();wrong['unassigned_reserve']=100
 (tmp_path/'state/dividend_sgov_ownership.json').write_text(json.dumps(wrong))
 target=tmp_path/'results/dividend_paper_trade_performance.json'
 target.parent.mkdir()
 target.write_text('UNCHANGED')
 with pytest.raises(ValueError,match='Current SGOV principal'):
  write_dividend_paper_trade_performance(tmp_path)
 assert target.read_text()=='UNCHANGED'
