# Trade Dividend Bot System Architecture

## Purpose

The Trade Dividend Bot is a paper-only portfolio research, ranking, allocation, management, and reporting system designed to maximize sustainable income plus growth.

## Execution Flow

```text
Market Regime
→ Market Intelligence
→ Momentum Score
→ Entry Score
→ Conviction
→ Dividend Ranking
→ Opportunity Pairing
→ Portfolio Decision
→ Capital Allocation
→ Portfolio Construction
→ Portfolio Rebalance
→ Income Reinvestment
→ Portfolio Lifecycle
→ Daily Portfolio Command Center
→ Weekly Portfolio Review
→ Strategy Performance Analytics
→ Monthly Portfolio Review
```

## Control Layer

### stage_input_adapters.py

Transforms upstream report schemas into the keyword arguments accepted by downstream builders. It preserves the public interfaces of existing modules while enabling semantic stage-to-stage data flow.

### master_portfolio_orchestrator.py

Validates the expected stage artifacts, records available, missing, and invalid stages, and produces the consolidated orchestration report.

### run_daily_dividend_cycle.py

Executes the complete paper-only cycle in approved order, writes all stage JSON artifacts, runs orchestration, and writes consolidated cycle JSON and Markdown reports.

## Layer Responsibilities

### Intelligence Layer

Market Regime, Market Intelligence, Momentum, Entry, and Conviction convert evidence into normalized portfolio context and scores.

### Opportunity Layer

Dividend Ranking and Opportunity Pairing compare total-market income and growth opportunities. Opportunity Pairing preserves the Self-Funding ETF Rule.

### Decision Layer

Portfolio Decision combines opportunity, conviction, entry, momentum, dividend ranking, self-funding, and risk-adjustment evidence.

### Capital Layer

Capital Allocation and Portfolio Construction convert ranked decisions into paper-only dollar and position recommendations while preserving reserve and concentration rules.

### Management Layer

Portfolio Rebalance, Income Reinvestment, and Portfolio Lifecycle determine hold, increase, reduce, exit-to-SGOV, re-entry, and reinvestment guidance.

### Executive Layer

Daily, Weekly, Strategy Analytics, and Monthly reports consolidate operational status, performance, risk, income, and recommendations.

## Data Contracts

Each stage produces a JSON-serializable mapping with module metadata, safety flags, warnings, errors, and stage-specific payload fields.

Required common safety values:

- paper_trade_mode=True
- reporting_only=True
- live_trading_enabled=False
- broker_execution_enabled=False

## Status Semantics

- COMPLETE: all required stage artifacts are available and valid.
- PARTIAL: one or more optional or expected stage artifacts are absent.
- ERROR: execution or validation errors exist.

A COMPLETE status confirms pipeline execution and schema validity. It does not independently guarantee the quality or freshness of source evidence.

## Portfolio Philosophy

- Income and growth are optimized together.
- Higher yield alone is insufficient.
- Higher growth alone is insufficient.
- Holdings remain allocated until objective sale evidence is present.
- Released capital is staged in SGOV before re-entry or reassignment.
- Additional cash rewards the strongest current holdings according to rank and limits.
- Every opportunity is evaluated on its own merit.

## Safety Boundary

The Version 1.0 architecture is reporting-only. It does not connect to a broker, place orders, submit trades, or mutate a live brokerage account.
