# Agentic ETF Backtest - Project Status

## Purpose

This project stores ChatGPT-generated ETF trading or allocation code so it can be run, validated, and backtested session by session.

## Current State

- Project scaffold created.
- Universe configuration updated with the first uploaded strategy symbol set.
- Universe validation script updated to fetch price and dividend data through `yfinance`.
- Changelog initialized.
- Python runner confirmed with `py` using Python 3.14.6.
- Runtime dependencies captured in `requirements.txt`.
- Universe validator now writes `universe_validation_report.csv`.
- Iteration snapshot helper added for OneDrive Documents backups.
- Milestone 2 downloader added to write daily historical OHLCV/dividend CSVs.
- Milestone 3 indicator and signal model files added using the approved strict rules.
- Pair signal concentration analyzer added with independent MST and XXRP rows.
- Milestone 4 portfolio accounting engine and cycle tests added.
- Baseline backtest runner added for local-data model and re-entry comparisons.
- Milestone 6 dividend engine and accounting tests added.
- Milestone 7 earnings-date downloader and cache workflow added.
- Milestone 7 earnings engine, validation, backtest, and impact comparison completed.
- Milestone 8 performance report generator added.
- Milestone 9A focused COIW/CONL A-only re-entry experiment added.
- Milestone 9B independent COIW/CONL sleeve experiment added.
- Milestone 9C all-pairs independent sleeve experiment added.
- Milestone 10 hybrid portfolio experiment added.
- Milestone 11 weighted hybrid portfolio optimizer added.
- Milestone 12 walk-forward validation added with explicit inception-coverage checks.
- Milestone 14 PAPER ONLY Strength Weighted Hybrid engine initialized.
- Milestone 15 signal-aware paper initialization completed.
- Milestone 16 daily paper trading automation completed.
- Milestone 17 strategy health dashboard completed and integrated into the daily cycle.
- Milestone 18 live readiness tracker completed and integrated into the daily cycle.
- Milestone 19 weekly portfolio review completed and scheduled through the Friday daily cycle.
- Gmail SMTP daily decision-report delivery added; awaiting app-password configuration.

## Latest Validation

- Date: 2026-06-21
- Command: `python validate_universe.py`
- Result: Passed
- Universe: 31 symbols
- Date Range: 2026-01-01 to 2026-06-18
- Data Rows Per Symbol: 115
- First Data Date: 2026-01-02
- Last Data Date: 2026-06-17
- Passed: 31
- Failed: 0
- Report: `universe_validation_report.csv`

## Latest Historical Data Download

- Date: 2026-06-21
- Command: `python download_historical_data.py`
- Result: Passed
- Universe: 31 symbols
- Symbol CSVs Written: 31
- Data Rows Per Symbol: 115
- First Data Date: 2026-01-02
- Last Data Date: 2026-06-17
- Passed: 31
- Failed: 0
- Data Folder: `historical_data/daily`
- Summary Report: `downloader_summary_report.csv`

## Latest Signal Model Test

- Date: 2026-06-21
- Command: `python test_signals.py`
- Result: Passed
- Daily Rows Tested: 690
- Period: 2026-01-02 to 2026-06-17
- Underlying Series: AMD, NVDA, TSLA, MSTR
- Special Series: MST from MSTR; XXRP from XXRP
- Output: `signal_test_output.txt`
- Assertions: Passed
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`
- Signal Counts:
  - AMD: 47 BUY, 49 HOLD, 19 SELL
  - NVDA: 25 BUY, 56 HOLD, 34 SELL
  - TSLA: 13 BUY, 53 HOLD, 49 SELL
  - MSTR: 19 BUY, 50 HOLD, 46 SELL
  - MST: 19 BUY, 50 HOLD, 46 SELL
  - XXRP: 0 BUY, 49 HOLD, 66 SELL

## Latest Pair Signal Analysis

- Date: 2026-06-21
- Command: `python analyze_pair_signals.py`
- Result: Passed
- Analysis Rows: 11
- Days Per Row: 115
- Standard Pair Rows: 9
- Independent Special Rows: MST from MSTR; XXRP from XXRP
- 95%+ BUY Rows: 0
- 95%+ SELL Rows: 0
- Assertions: Passed
- Output: `pair_signal_analysis.csv`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Portfolio Engine Test

- Date: 2026-06-21
- Command: `python test_portfolio_engine.py`
- Result: Passed
- Starting Capital Per Pair: $50
- Initial Allocation: 70% A / 30% B
- Re-entry Modes Tested: proportional restoration; fixed 70/30 reset
- Cycle Tested: BUY -> SELL -> SGOV yield -> BUY
- Proportional Ending Value: $54.54
- Fixed 70/30 Ending Value: $54.54
- MST/XXRP Independent Ending Value: $54.42
- Trade Count Per Tested Cycle: 2
- SGOV Entries/Exits Per Tested Cycle: 1/1
- Accounting Assertions: Passed
- Output: `portfolio_engine_test_output.txt`
- Deferred: dividends, earnings exits, performance metrics
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Baseline Backtest

- Date: 2026-06-21
- Command: `python baseline_backtest.py`
- Result: Passed
- Result Rows: 38
- Starting Capital Per Pair: $50
- Standard Pairs: 9
- Models: Underlying; ETF
- Re-entry Modes: proportional restoration; fixed 70/30 reset
- Special Pair: MST and XXRP as independent sleeves
- Execution: prior-close signal executed at the next close
- SGOV Accrual: adjusted-close daily return while parked
- Best Result: AMDW / AMDL, Underlying, fixed 70/30, $91.889669 final value
- Lowest Result: MST / XXRP, Independent, $28.417643 final value
- Accounting Assertions: Passed
- Output: `baseline_backtest_results.csv`
- Excluded: A/B dividends, earnings exits, performance-report metrics
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Dividend Backtest

- Date: 2026-06-21
- Commands: `python test_dividend_engine.py`; `python dividend_backtest.py`
- Result: Passed
- Result Rows: 38
- Income Side: A only
- Reinvestment: immediate 50% A / 50% B
- SGOV Handling: pending dividend portions held until the corresponding BUY
- Dividend Accounting Assertions: Passed
- Baseline Comparison Assertions: Passed
- Scenario-Row Dividends Received Total: $176.698698
- Best Result: AMDW / AMDL, Underlying, fixed 70/30, $108.205387 final value
- Lowest Result: COIW / CONL, Underlying, fixed 70/30, $31.529632 final value
- Output: `dividend_backtest_results.csv`
- Excluded: earnings exits and dividend-timing optimization
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Earnings Backtest

- Date: 2026-06-21
- Commands: `python download_earnings_dates.py`; `python test_earnings_engine.py`; `python earnings_backtest.py`
- Result: Passed
- Earnings Caches: 9/9 passed
- Result Rows: 38
- Forced Exit: one trading day before cached underlying earnings date
- Re-entry: current-day BUY check beginning first trading day after earnings
- MST/XXRP: MST follows MSTR earnings; XXRP remains independent
- Earnings Accounting Assertions: Passed
- GLD Exclusion Assertion: Passed
- Final Value Improved: 23 scenarios
- Final Value Worsened: 11 scenarios
- Final Value Unchanged: 4 GLD scenarios
- Max Drawdown Improved: 32 scenarios
- Max Drawdown Worsened: 2 scenarios
- Max Drawdown Unchanged: 4 GLD scenarios
- Best Dollar Impact: AVGW / AVGX, Underlying, proportional, +$17.600147
- Worst Dollar Impact: COIW / CONL, ETF, proportional, -$13.763305
- Best Final Value: AMDW / AMDL, Underlying, proportional, $122.068477
- Outputs: `earnings_backtest_results.csv`; `earnings_impact_summary.csv`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Performance Report

- Date: 2026-06-21
- Command: `python generate_performance_report.py`
- Result: Passed
- Pair Rows: 38
- Portfolio Configurations: 4
- Pairs Per Portfolio: 10
- Starting Capital Per Portfolio: $500
- Best Portfolio: Underlying / proportional
- Best Portfolio Ending Capital: $545.851548
- Best Portfolio Return: 9.170310%
- Best Portfolio Average Drawdown: -25.720798%
- Best Pair Combination: AMDW / AMDL, Underlying, proportional, $122.068477
- Worst Pair Combination: COIW / CONL, Underlying, fixed 70/30, $22.043101
- Best Portfolio Dividends Received: $37.175474
- Best Portfolio Earnings Exits: 16
- Reconciliation Assertions: Passed
- Outputs: `performance_report.csv`; `performance_summary.md`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest COIW / CONL Re-entry Test

- Date: 2026-06-21
- Command: `python run_coiw_reentry_test.py`
- Result: Passed
- Scope: COIW / CONL only
- New Mode: `a_only_reentry`
- Principal Re-entry: 100% COIW / 0% CONL
- Dividend Reinvestment: 50% COIW / 50% CONL
- Underlying A-only Final Value: $22.863297
- Underlying Proportional Final Value: $22.215754
- Underlying Fixed 70/30 Final Value: $22.043101
- A-only Improvement vs Proportional: +$0.647543
- A-only Improvement vs Fixed 70/30: +$0.820196
- ETF A-only Final Value: $26.509570
- ETF Finding: unchanged because no SGOV exit/BUY re-entry occurred
- Allocation Validation: Passed
- Dividend-to-CONL Validation: Passed
- Accounting Reconciliation: Passed
- Outputs: `coiw_reentry_test.csv`; `coiw_reentry_summary.md`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest COIW / CONL Independent Sleeve Test

- Date: 2026-06-21
- Command: `python run_coiw_independent_sleeve_test.py`
- Result: Passed
- Current Pair Final Value: $22.215754
- A-only Final Value: $22.863297
- Independent Sleeve Final Value: $26.509570
- Independent Improvement vs Current Pair: +$4.293816
- Independent Improvement vs A-only: +$3.646273
- Current Pair Max Drawdown: -60.187867%
- Independent Max Drawdown: -55.982430%
- Drawdown Improvement vs Current Pair: +4.205437 percentage points
- Independent Trades: 2
- Independent SGOV Entries: 2
- Independent Days in SGOV: 88
- COIW Earnings Exits: 1
- CONL Earnings Exits: 1
- Different Signal Days: 0
- Independent State Days: 0
- Finding: COIW and CONL had identical signals, so independent controls did not diverge during this period
- Output: `coiw_independent_sleeve_test.csv`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest All-Pairs Independent Sleeve Test

- Date: 2026-06-21
- Command: `python run_all_independent_sleeves.py`
- Result: Passed
- Comparison Rows: 20
- Current Portfolio Final Value: $545.851548
- Independent Portfolio Final Value: $500.005642
- Difference: -$45.845906
- Difference Percent: -8.398970%
- Current Average Drawdown: -25.720798%
- Independent Average Drawdown: -26.169733%
- Best Improving Pair: COIW / CONL, +$4.293816
- Worst Worsening Pair: AMDW / AMDL, -$29.841067
- Pairs Helped: GOOW / GGLL; COIW / CONL
- Pairs Hurt: AMDW / AMDL; NVDW / NVDX; NFLW / NFLU; AVGW / AVGX; TSLW / TSLL
- Pairs Unchanged: GLDW / NUGT; PLTW / PLTU; MST / XXRP
- Finding: independent sleeves should not replace the current architecture portfolio-wide based on this period
- State Independence Validation: Passed
- Dividend Waiting Validation: Passed
- Earnings Exit Validation: Passed
- MST/XXRP Unchanged Validation: Passed
- Accounting Reconciliation: Passed
- Outputs: `independent_sleeve_results.csv`; `independent_sleeve_summary.md`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Hybrid Portfolio Test

- Date: 2026-06-21
- Command: `python run_hybrid_portfolio_test.py`
- Result: Passed
- Starting Capital: $500
- Hybrid Ending Capital: $551.009896
- Hybrid Profit/Loss: +$51.009896
- Hybrid Return: +10.201979%
- Hybrid Portfolio Max Drawdown: -16.190966%
- Hybrid Average Pair Drawdown: -25.137808%
- Dividends Received: $35.987675
- Earnings Exits: 18
- SGOV Entries: 34
- SGOV Pair-Days: 730
- Best Pair: AMDW / AMDL, $122.068477
- Worst Pair: COIW / CONL, $26.509570
- Current Best Ending Capital: $545.851548
- Improvement vs Current Best: +$5.158348
- Improvement Percent: +0.945009%
- Current Best Portfolio Max Drawdown: -16.190966%
- Portfolio Drawdown Change: 0.000000 percentage points
- Starting Capital Validation: Passed
- Pair Source Reconciliation: Passed
- Portfolio Sum Reconciliation: Passed
- MST/XXRP Preservation: Passed
- Dividend and Earnings Reconciliation: Passed
- Outputs: `hybrid_portfolio_results.csv`; `hybrid_portfolio_summary.md`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Weighted Hybrid Portfolio Test

- Date: 2026-06-21
- Command: `python run_weighted_hybrid_optimization.py`
- Result: Passed
- Starting Capital Per Portfolio: $500
- Equal Weight Ending Capital: $551.009896
- Equal Weight Return: +10.201979%
- Equal Weight Max Drawdown: -16.190966%
- Strength Weighted Ending Capital: $609.313321
- Strength Weighted Return: +21.862664%
- Strength Weighted Max Drawdown: -11.372222%
- Risk Adjusted Ending Capital: $657.206568
- Risk Adjusted Return: +31.441314%
- Risk Adjusted Max Drawdown: -8.757964%
- Best Historical Result: Risk_Adjusted_Hybrid
- Improvement vs Equal Weight: +$106.196672
- Improvement Percent vs Equal Ending Value: +19.273097%
- Risk Allocation Bounds: $20 minimum; $90 maximum
- Allocation Sum Validation: Passed
- Hybrid Architecture Validation: Passed
- Dividend and Earnings Reconciliation: Passed
- Interpretation: weighting warrants out-of-sample testing; risk-adjusted weights are in-sample and are not yet approved for live allocation.
- Outputs: `weighted_hybrid_results.csv`; `weighted_hybrid_summary.md`

## Latest Walk-Forward Validation

- Date: 2026-06-21
- Command: `python run_walk_forward_validation.py`
- Result: Completed with historical-coverage limitations
- Period A Requested: 2025-01-01 through 2025-06-30
- Period A Result: Unavailable
- Period A Missing History: AMDW, GLDW, GOOW, AVGW
- Period B Requested: 2025-07-01 through 2025-12-31
- Period B Common Runnable Range: 2025-10-30 through 2025-12-31
- Period B Equal Weight: $499.493560; -0.101288%; -5.457068% max drawdown
- Period B Strength Weighted: $496.445986; -0.710803%; -5.894323% max drawdown
- Period B Risk Adjusted: $503.896844; +0.779369%; -4.905328% max drawdown
- Period C Runnable Range: 2026-01-02 through 2026-06-17
- Period C Equal Weight: $551.009918; +10.201984%; -16.190963% max drawdown
- Period C Strength Weighted: $609.313347; +21.862669%; -11.372218% max drawdown
- Period C Risk Adjusted: $657.206597; +31.441319%; -8.757960% max drawdown
- Strength vs Equal: Strength won 1 of 2 runnable periods
- Risk Adjusted vs Equal: Risk Adjusted won 2 of 2 runnable periods
- Live Recommendation: Equal Weight pending complete out-of-sample validation
- Allocation Validation: Passed for all runnable portfolios
- Hybrid Architecture Validation: Passed
- Dividend and Earnings Reconciliation: Passed
- Outputs: `walk_forward_results.csv`; `walk_forward_summary.md`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Paper Trading Engine Validation

- Date: 2026-06-21
- Commands: `python test_paper_trading_engine.py`; `python paper_trading_engine.py`
- Result: Passed
- Safety Mode: PAPER ONLY - NO REAL TRADES EXECUTED
- Market Data Source: Yahoo Finance daily data
- State Date: 2026-06-18
- Starting Paper Capital: $500.000000
- Initial Paper Portfolio Value: $500.000000
- Pair Buckets: 10
- Pair-Managed Buckets: 7
- Independent-Sleeve Buckets: 3
- Initial Simulated Opening Log Rows: 20
- Same-Date Duplicate Log Rows: 0
- Approved Allocation Validation: Passed
- State Persistence Validation: Passed
- Append-Only Log Validation: Passed
- Daily Report Validation: Passed
- Broker/Order API Dependency Check: Passed
- Current Pair Recommendations: AMDW/AMDL BUY; AVGW/AVGX HOLD; NVDW/NVDX HOLD; GLDW/NUGT SELL; NFLW/NFLU SELL; TSLW/TSLL SELL; PLTW/PLTU SELL
- Current Independent Recommendations: GOOW/GGLL SELL/SELL; COIW/CONL SELL/SELL; MST/XXRP SELL/SELL
- Outputs: `paper_state.json`; `paper_trade_log.csv`; `daily_paper_report.md`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Signal-Aware Paper Initialization

- Date: 2026-06-22
- Commands: `python test_signal_aware_initialization.py`; `python paper_trading_engine.py --reinitialize-signal-aware`
- Result: Passed
- State Date: 2026-06-18
- Total Paper Capital: $500.000000
- ETF Exposure: $190.000000
- SGOV Exposure: $310.000000
- Fully Invested Pairs: 3
- Fully Parked Pairs: 7
- Mixed-State Pairs Today: 0
- Invested: AMDW/AMDL (BUY), AVGW/AVGX (HOLD), NVDW/NVDX (HOLD)
- Parked: GOOW/GGLL, GLDW/NUGT, NFLW/NFLU, TSLW/TSLL, PLTW/PLTU, COIW/CONL, MST/XXRP
- Independent Sleeve State Fields: `a_in_sgov`; `b_in_sgov`
- BUY Initialization Validation: Passed
- HOLD Initialization Validation: Passed
- SELL-to-SGOV Initialization Validation: Passed
- Independent Mixed-Sleeve Validation: Passed
- Capital Reconciliation: Passed
- Broker/Order API Dependency Check: Passed
- Append-Only Audit Log Preserved: 40 total rows after migration
- Outputs: `paper_state.json`; `daily_paper_report.md`; `initialization_comparison.md`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Daily Paper Cycle

- Date Run: 2026-06-22
- Market Data Through: 2026-06-18
- Command: `python run_daily_paper_cycle.py`
- Result: Passed
- Safety Mode: PAPER ONLY - NO REAL TRADES EXECUTED
- Same Market Date Already Processed: Yes
- New Paper Trade Log Rows: 0
- Portfolio Snapshot Rows: 1
- Portfolio Value: $500.000000
- ETF Exposure: $190.000000
- SGOV Exposure: $310.000000
- Cash Flow Today: $0.000000
- Dividends Today: $0.000000
- Open Buckets: 3
- SGOV Buckets: 7
- New BUY Signals: None
- New SELL Signals: None
- New Earnings Exits: None
- Next-Day Action: No transitions; maintain AMDW/AMDL, AVGW/AVGX, and NVDW/NVDX ETF positions; all other buckets remain in SGOV.
- State Update Validation: Passed
- Report Generation Validation: Passed
- Append-Only Log Validation: Passed
- Same-Date Idempotency Validation: Passed
- Portfolio Reconciliation: Passed
- Broker/Order API Dependency Check: Passed
- Outputs: `paper_state.json`; `paper_trade_log.csv`; `daily_paper_report.md`; `portfolio_snapshot.csv`; `daily_change_summary.md`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Strategy Health Dashboard

- Date: 2026-06-22
- Command: `python generate_strategy_health_dashboard.py`
- Result: Passed
- Paper Data Through: 2026-06-18
- Days Running: 1 unique market snapshot
- Starting Portfolio Value: $500.000000
- Current Portfolio Value: $500.000000
- Total Return: 0.000000%
- Annualized Return Estimate: 0.000000% (suppressed until at least two snapshots)
- ETF Exposure: $190.000000
- SGOV Exposure: $310.000000
- Current Signals: 1 BUY; 10 SELL; 2 HOLD across 13 decision streams
- ETF-to-SGOV Transitions: 0
- SGOV-to-ETF Transitions: 0
- Earnings Exits/Re-entries: 0 / 0
- Dividends Received/Reinvested: $0.000000 / $0.000000
- Current/Maximum/Average Drawdown: 0.000000% / 0.000000% / 0.000000%
- Backtest Drawdown Expectation: -11.372222%
- Alerts: 0
- Abnormal Pairs: None detected
- Accounting/SGOV/Earnings Consistency: Passed
- Within Expected Risk Parameters: Yes, with insufficient duration for performance conclusions
- Future Live Deployment Eligible: No; requires at least 60 unique clean paper-market days
- Daily Cycle Integration: Passed
- Outputs: `strategy_health_report.md`; `strategy_health.csv`; `pair_health.csv`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Live Readiness Tracker

- Date: 2026-06-22
- Command: `python generate_live_readiness_tracker.py`
- Result: Passed
- Paper Data Through: 2026-06-18
- Paper Trading Days Completed: 1
- Consecutive Clean Validation Days: 1
- Days Remaining Until Operational Eligibility: 29
- Signal Changes Observed: 0
- Dividend Events Observed: 0
- Earnings Events Observed: 0
- ETF-to-SGOV / SGOV-to-ETF Transitions: 0 / 0
- Maximum Drawdown: 0.000000%
- Portfolio Return: 0.000000%
- Gate 30 Operational Validation: IN_PROGRESS; 3.333333%; 29 days remaining
- Gate 60 Limited Live Capital: IN_PROGRESS; 1.666667%; 59 days remaining
- Gate 90 Production Candidate: IN_PROGRESS; 1.111111%; 89 days remaining
- Overall Live Readiness: 1.111111%
- Same-Date Idempotency Validation: Passed
- Daily Cycle Integration: Passed
- Outputs: `live_readiness_report.md`; `live_readiness.csv`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Weekly Portfolio Review

- Date: 2026-06-22
- Review Week Ending: 2026-06-18
- Command: `python generate_weekly_portfolio_review.py`
- Result: Passed
- Current Portfolio Value: $500.000000
- Weekly Gain/Loss: $0.000000
- ETF / SGOV Exposure: $190.000000 / $310.000000
- New Signals: 1 BUY; 10 SELL; 2 HOLD initial observations
- ETF-to-SGOV / SGOV-to-ETF Transitions: 0 / 0
- Dividends Received/Reinvested: $0.000000 / $0.000000
- Earnings Exits/Re-entries: 0 / 0
- Pair Ranking: all ten pairs tied at 0.000000% return
- Current / Maximum Drawdown: 0.000000% / 0.000000%
- Backtest Drawdown Expectation: -11.372222%
- Live Readiness: 1.111111%; 1 day completed
- Gate Days Remaining: 29 / 59 / 89
- Abnormal Pair Behavior: None detected
- Friday Daily Cycle Integration: Passed
- Reconciliation to Health/Readiness/Snapshot: Passed
- Output: `weekly_portfolio_review.md`
- Published To: `C:\Users\pmapp\OneDrive\Documents\RobinHood_TradeBot_Output`

## Latest Email Delivery Configuration

- Date: 2026-06-22
- Provider: Gmail SMTP over SSL
- Sender: `percyagenticmay27@gmail.com`
- Recipient: `percyagenticmay27@gmail.com`
- Schedule: Weekdays at 3:30 PM Central after the daily paper cycle
- Attachments: `daily_paper_report.md`; `daily_change_summary.md`; `strategy_health_report.md`; `live_readiness_report.md`
- CSV/JSON/State/Log Attachments: Excluded
- Credential Source: `GMAIL_APP_PASSWORD` environment variable only
- Credential Stored In Repository: No
- Duplicate-Send Protection: Enabled by report date and recipient
- Fake SMTP Composition Test: Passed
- Real Test Email Sent: Yes, 2026-06-22
- Gmail Authentication: Persistent Windows User environment fallback enabled
- Automation Updated: Passed

## Session Workflow

1. Add or update generated strategy code.
2. Validate ETF universe and configuration.
3. Run the requested backtest.
4. Record results, assumptions, and follow-up work here.
5. Save a timestamped iteration snapshot to OneDrive Documents.

## Snapshot Workflow

- Command: `python snapshot_iteration.py`
- Destination: `C:\Users\pmapp\OneDrive\Documents\agentic_etf_backtest_snapshots`
- Latest Snapshot: newest `iteration_*` folder in the destination
- Files copied: `PROJECT_STATUS.md`, `CHANGELOG.md`, `pairs_config.py`, `validate_universe.py`, `requirements.txt`, `universe_validation_report.csv`

## Open Items

- Obtain a complete out-of-sample period after all ten pair instruments exist, or approve a reduced-universe/proxy test design.
- Use `python run_daily_paper_cycle.py` as the operational daily command.
- Configure `GMAIL_APP_PASSWORD` as a persistent user environment variable before enabling real Gmail delivery.
- Review strategy results and approve the next milestone.
