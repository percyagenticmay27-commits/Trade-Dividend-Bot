# Trade Dividend Bot Module Index

## Core Pipeline

| Order | Module | Responsibility |
|---:|---|---|
| 1 | market_regime_engine.py | Classifies broad market conditions and reserve context. |
| 2 | market_intelligence_engine.py | Summarizes company, sector, macro, and narrative evidence. |
| 3 | momentum_score_engine.py | Scores directional and relative momentum. |
| 4 | entry_score_engine.py | Evaluates entry timing independently from long-term opportunity quality. |
| 5 | conviction_engine.py | Combines supporting evidence into conviction guidance. |
| 6 | dividend_ranking_engine.py | Ranks dividend opportunities using quality, growth, safety, momentum, and valuation. |
| 7 | opportunity_pairing_engine.py | Ranks income-plus-growth opportunities and enforces the Self-Funding ETF Rule. |
| 8 | portfolio_decision_engine.py | Converts upstream evidence into paper-only allocation actions. |
| 9 | capital_allocation_engine.py | Assigns paper capital by score, account size, reserve, and position constraints. |
| 10 | portfolio_construction_engine.py | Builds the recommended paper portfolio from approved allocations. |
| 11 | portfolio_rebalance_engine.py | Recommends hold, increase, reduce, replace, re-entry, and SGOV staging actions. |
| 12 | income_reinvestment_engine.py | Directs distributions to self-funding, pair growth, cash shield, or rotation roles. |
| 13 | portfolio_lifecycle_engine.py | Consolidates holding state and lifecycle recommendations. |
| 14 | daily_portfolio_command_center.py | Produces the daily executive portfolio view. |
| 15 | weekly_portfolio_review_engine.py | Aggregates weekly performance, actions, and risks. |
| 16 | strategy_performance_analytics_engine.py | Compares paper strategy outcomes and signal effectiveness. |
| 17 | monthly_portfolio_review_engine.py | Aggregates monthly return, income, reserve, and strategy results. |

## Control and Integration

| Module | Responsibility |
|---|---|
| stage_input_adapters.py | Adapts upstream report payloads to downstream builder signatures. |
| master_portfolio_orchestrator.py | Validates stage availability and produces the orchestration report. |
| run_daily_dividend_cycle.py | Executes all stages and writes the consolidated daily cycle outputs. |
| version_1_0_release_audit.py | Performs static release inventory, compile, safety, and test-reference auditing. |

## Principal Tests

- test_stage_input_adapters.py
- test_master_portfolio_orchestrator.py
- test_run_daily_dividend_cycle.py
- test_daily_cycle_integration.py
- test_version_1_0_release_audit.py

Each major engine also has dedicated pytest coverage or is referenced by grouped project tests.

## Principal Runtime Outputs

- market_regime_report.json
- market_intelligence_report.json
- momentum_score_report.json
- entry_score_report.json
- conviction_report.json
- dividend_rankings.json
- opportunity_pairing_report.json
- portfolio_decision_report.json
- capital_allocation_report.json
- portfolio_construction_report.json
- portfolio_rebalance_report.json
- income_reinvestment_report.json
- portfolio_lifecycle_report.json
- daily_portfolio_command_center.json
- weekly_portfolio_review.json
- strategy_performance_analytics.json
- monthly_portfolio_review.json
- master_portfolio_orchestration_report.json
- daily_dividend_cycle_report.json
- daily_dividend_cycle_report.md

## Release Audit Outputs

- version_1_0_release_audit.json
- version_1_0_release_audit.md

## Safety Classification

All Version 1.0 modules are paper-only and reporting-only. No module in the frozen release is authorized to place or submit live orders.
