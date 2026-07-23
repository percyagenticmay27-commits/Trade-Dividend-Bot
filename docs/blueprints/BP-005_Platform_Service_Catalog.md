# BP-005 Platform Service Catalog

**Version:** 1.0.0  
**Status:** FROZEN  
**Scope:** Shared platform services for the paper-only Investment Intelligence Platform.

## 1. Purpose

This catalog defines service ownership, responsibilities, inputs, outputs, and dependency boundaries. Shared services are strategy-neutral. Dividend, Swing, Options, and future strategies consume these services but do not own them.

## 2. Global Rules

- `paper_trade_mode=True` is mandatory.
- No broker execution or real order placement.
- Platform services must not import strategy-specific modules.
- Missing optional evidence produces warnings or neutral values according to the owning module contract.
- Evidence and decisions are append-only.
- Strategy reports and audits remain isolated by `strategy_id`.

## 3. Foundation Services

### Platform Configuration Service
Owns platform settings, paths, refresh intervals, feature flags, and paper-only enforcement.

### Identifier Service
Creates UUID primary identifiers and human-friendly external identifiers.

### Version Registry Service
Tracks platform, blueprint, constitution, module, schema, and strategy versions.

### Serialization Service
Provides deterministic JSON, CSV, and Markdown serialization without investment logic.

### Logging and Diagnostics Service
Produces operational logs, health status, warnings, and diagnostics while protecting secrets.

## 4. Company Intelligence Services

### Company Registry Service
Maintains one canonical company identity and symbol history.

### Master Company Intelligence Profile Service
Creates and updates exactly one MCIP per company. It stores shared facts and calculated intelligence, never strategy decisions.

### Discovery Service
Finds candidate companies and records discovery sources, dates, and scores.

### Fundamental Intelligence Service
Maintains revenue, earnings, margins, cash flow, leverage, valuation, and financial-health evidence.

### Growth Intelligence Service
Maintains historical and forward growth measures and revisions.

### Income Intelligence Service
Maintains dividend history, yield, growth, coverage, continuity, and safety facts for shared use.

### Risk Intelligence Service
Maintains financial, market, earnings, accounting, macro, regulatory, liquidity, and concentration risks.

### Technical Indicator Service
Calculates indicators such as SMA, EMA, RSI, MACD, ATR, VWAP, volume, trend, and relative strength. It does not create entry or exit decisions.

### Market Intelligence Service
Maintains news, analyst actions, institutional activity, insider activity, sentiment, and market context.

### Earnings Intelligence Service
Maintains earnings dates, estimates, results, surprises, revisions, and event risk.

### Theme Intelligence Service
Maintains sector, industry, theme membership, and theme momentum.

### Watchlist Intelligence Service
Maintains shared watchlist status and evidence. Strategy-specific watchlists remain separately attributable.

## 5. Evidence and Governance Services

### Evidence Repository Service
Stores immutable evidence records and append entries. Corrections are new append entries, never overwrites.

### AI CIO Decision Service
Applies the Constitution and creates the sole automated investment decision per strategy evaluation.

### Committee Coordination Service
Collects committee analysis, questions, and recommendations. It never votes or decides.

### Decision Ledger Service
Stores decisions, state transitions, supersession links, implementation status, and outcome history.

### Investor Override Service
Allows only the investor to override a decision, requiring a reason, audit trail, and preservation of the original decision.

## 6. Portfolio Services

### Portfolio Service
Owns the consolidated paper portfolio and holdings.

### Position Attribution Service
Attributes every position, lot, return, cost basis, income, and realized result to a strategy.

### Allocation Service
Applies portfolio and strategy allocation constraints in paper mode.

### Lifecycle Service
Manages candidate, opened, held, reduced, closed, archived, and re-entry states.

### Wealth Attribution Service
Calculates return, income, realized and unrealized results by company, strategy, theme, and period.

## 7. Strategy Framework Services

### Strategy Registry Service
Registers strategy metadata, version, capabilities, required intelligence, reports, audits, and lifecycle state.

### Strategy Evaluation Service
Provides a standard contract for a strategy to interpret MCIP intelligence and create a strategy-specific evaluation.

### Strategy Lifecycle Service
Manages installed, configured, paper-validation, operational, suspended, and archived states.

## 8. Reporting, Audit, and Learning Services

### Reporting Service
Renders shared templates to JSON, CSV, and Markdown. Report content and metrics are supplied by one strategy at a time.

### Audit Service
Executes platform audits and isolated strategy audits using common rendering and severity rules.

### Learning Repository Service
Stores platform-wide and strategy-attributed lessons without merging distinct strategy outcomes.

### Notification Service
Delivers approved reports and alerts through configured paper-only operational channels.

## 9. Service Dependency Rule

Foundation -> Company Intelligence -> Evidence -> Governance -> Portfolio -> Strategy Framework -> Reporting/Audit/Learning -> Strategy Packages.

A lower layer must never depend on a higher layer. Shared services must never depend on Dividend, Swing, Options, or future strategy implementations.

## 10. Freeze Statement

This service catalog is frozen for Platform Version 1.0. Changes require an approved ADR and corresponding updates to BP-006, BP-007, and BP-008.