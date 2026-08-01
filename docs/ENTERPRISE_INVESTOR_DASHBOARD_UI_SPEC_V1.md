# Enterprise Investor Dashboard UI Specification v1.0

## Purpose

This document is the authoritative design specification for the Enterprise Investor Dashboard and its strategy-level KPI views.

It exists so the intended dashboard behavior can be verified during local development, testing, and DigitalOcean deployment. If a section is missing, empty, renamed, or rendered incorrectly in production, this document defines what was supposed to be implemented.

The dashboard remains reporting-only and paper-only. It must not place trades, move capital, alter allocations, or override strategy decisions.

## Architectural Scope

The Investor Dashboard answers:

> How is the complete investment enterprise performing across all registered strategies?

It presents:

1. Enterprise totals across all registered strategies.
2. Contributor drill-downs showing how each strategy contributed to each total.
3. Individual strategy KPI analytics.
4. Enterprise and per-strategy watchlists.
5. Portfolio holdings and positions with clickable decision rationale, committee scores, and supporting evidence.

The Enterprise Registry is the source of truth for which strategies exist. The dashboard must not hardcode Dividend, Swing, Options, Futures, or any other strategy name.

## Strategy-Agnostic Design Rule

All enterprise metrics use generic labels. Strategy-specific labels appear only inside a strategy's own KPI workspace.

Examples:

- Enterprise label: `Income`
- Dividend strategy detail: `Dividend Income`
- Options strategy detail: `Option Premium Income`
- Fixed-income strategy detail: `Interest Income`

At the enterprise level, all compatible income types contribute to the single `Income` total.

## Enterprise Summary KPI Cards

The top row contains enterprise-level KPI cards. Each card displays the total across all registered strategies that reported the metric.

Every card must show:

- Dollar amount first when the metric has monetary value.
- Percentage second when applicable.
- Reporting completeness, such as `3 of 4 strategies reported` when incomplete.
- A `More` or `Details` action.
- No silent conversion of missing strategy evidence to zero.

### Required Enterprise KPI Cards

#### Portfolio Value

Combined current portfolio value across all reporting strategies.

`Details` opens the contributor view showing portfolio value by strategy.

#### Allocated Capital

Total paper capital currently allocated to registered strategies.

`Details` shows each strategy's allocated amount and percentage of enterprise allocated capital.

#### Available Cash / Reserve

Enterprise-level unassigned paper cash and reserve.

The contributor view must distinguish centrally held reserve from cash retained inside individual strategies when the evidence contract supports that distinction.

#### Income

Total income from all strategies.

This includes, where reported:

- Dividends
- Option premium income
- Interest income
- Fixed-income distributions
- Other strategy income classifications

The top-level card remains labeled `Income`. Premium income must not require a separate enterprise card.

`Details` shows:

| Strategy | Strategy Type | Income Category | Income Amount | Contribution % | Evidence Status |
|---|---|---|---:|---:|---|

#### Performance

Combined enterprise performance using the approved enterprise performance methodology.

The contributor view shows each strategy's reported performance and contribution. It must clearly identify when strategies use different native measures and when normalization was required.

`Details` shows:

| Strategy | Native Performance Metric | Native Value | Normalized Contribution | Reporting Period | Evidence Status |
|---|---|---:|---:|---|---|

#### Realized P&L

Total realized profit and loss across all reporting strategies.

`Details` shows realized P&L by strategy, including reporting period and evidence source.

#### Unrealized P&L

Total unrealized profit and loss across all reporting strategies.

`Details` shows unrealized P&L by strategy and current open-position contribution.

#### Win Rate

Enterprise win-rate presentation for all strategies that publish compatible closed-decision or closed-trade evidence.

The total must use the approved weighted calculation based on wins and completed observations, not a simple average of strategy percentages unless that is the only supported evidence.

`Details` shows:

| Strategy | Wins | Losses | Completed Observations | Win Rate | Evidence Status |
|---|---:|---:|---:|---:|---|

#### Yield

Combined enterprise yield for strategies that publish yield-compatible evidence.

This includes fixed-income strategies but is not limited to a bot named `Fixed Income`.

`Details` shows each contributing strategy's yield, invested value, income basis, calculation method, and reporting completeness.

#### Capital Appreciation

Total capital appreciation across all reporting strategies.

`Details` shows the appreciation contribution from every strategy, including growth, swing, options, futures, dividend, and future registered strategies when they report compatible evidence.

#### Enterprise Health

Combined readiness, health, runtime, evidence freshness, and safety status across all registered strategies.

`Details` shows health and readiness for every strategy and identifies missing or stale evidence.

## More / Details Interaction Standard

All enterprise KPI cards use the same interaction pattern.

1. The user selects `More` or `Details`.
2. The One View Analysis workspace updates below the KPI cards.
3. The workspace does not create a separate browser page for every metric.
4. The selected metric remains visually highlighted.
5. The analysis workspace contains:
   - What is this?
   - How is it calculated?
   - Why does it matter?
   - Is this estimated?
   - Measurement period
   - Contributor table
   - Evidence completeness
   - AI CIO commentary
6. The contributor table lists every registered strategy, including strategies with missing evidence.
7. Missing evidence is displayed as `Not Reported`, never as an invented zero.

## Individual Strategy KPI Workspace

Below the enterprise totals, the dashboard provides a strategy selector, table, or tabs generated dynamically from the Enterprise Registry.

Each registered strategy receives its own KPI workspace.

### Common Strategy KPIs

Every strategy workspace should show these when evidence is available:

- Strategy name
- Strategy ID
- Strategy type and class
- Lifecycle status
- Runtime status
- Health
- Readiness
- Evidence status and freshness
- Allocated capital
- Portfolio value
- Realized P&L
- Unrealized P&L
- Income
- Return or native performance measure
- Win rate
- Position count
- Watchlist count
- Opportunity quality or equivalent strategy score

### Strategy-Specific KPIs

Strategy plugins may declare additional KPIs through their Registry v2 capability and artifact contracts.

Examples include:

- Dividend payment reliability
- Upcoming dividend payments
- Option premium collected
- Assignment exposure
- Futures margin usage
- Maximum drawdown
- Average holding period
- Opportunity Quality
- Entry Score
- Market regime alignment

The host dashboard renders declared KPIs generically. It must not require code changes for each new strategy.

## Watchlist Table

The KPI area must include a watchlist table.

The enterprise watchlist view combines watchlist records from every registered strategy while preserving strategy ownership.

### Required Columns

| Field | Description |
|---|---|
| Strategy | Strategy that owns the candidate |
| Symbol / Pair | Stock, ETF, option contract, futures contract, currency pair, or other instrument identifier |
| Instrument Type | Equity, ETF, option, future, pair, fixed income, or other registered type |
| Watchlist Status | Candidate, monitoring, promoted, demoted, rejected, pending, or strategy-defined normalized status |
| Opportunity / Quality Score | Strategy's approved opportunity-quality measure |
| Entry / Timing Score | Entry or timing measure when published; must remain separate from Opportunity Quality |
| Conviction | Strategy conviction score or classification |
| Risk | Risk score, classification, or principal risk flag |
| Market Regime | Regime context used by the strategy |
| Added Date | Date the candidate entered the watchlist |
| Last Updated | Evidence freshness timestamp |
| Decision Link | Opens the One View Decision Analysis workspace |

### Watchlist Filters

The table should support filtering by:

- Strategy
- Instrument type
- Watchlist status
- Score range
- Risk
- Market regime
- Evidence freshness

## Portfolio and Positions Table

The portfolio section must display all enterprise holdings and open positions while preserving the strategy that owns each position.

### Required Columns

| Field | Description |
|---|---|
| Strategy | Owning strategy |
| Symbol / Pair | Clickable instrument identifier |
| Instrument Type | Equity, ETF, option, future, pair, or other type |
| Quantity / Contracts | Position quantity or contract count |
| Cost Basis | Reported cost basis |
| Market Value | Current paper market value |
| Allocation | Dollar amount first, percentage second |
| Realized P&L | Realized result associated with the position when applicable |
| Unrealized P&L | Current unrealized result |
| Lifecycle Status | Active, monitoring, SGOV-protected, pending, replaced, closed, or normalized strategy state |
| Health / Risk | Position health and principal risk status |
| Last Updated | Evidence timestamp |

## Clickable Symbol / Pair Decision Analysis

Selecting a stock symbol, ETF, option contract, futures contract, or pair opens a One View Decision Analysis workspace.

This workspace explains why the instrument was selected and shows the decision evidence that existed at the time.

### Required Decision Analysis Sections

#### Decision Summary

- Strategy name and ID
- Instrument
- Decision type: watchlist, enter, hold, add, reduce, protect, replace, reject, or close
- Decision timestamp
- Current lifecycle status
- Plain-language reason the instrument was selected

#### Committee Scorecard

Show the score or vote from every participating committee or engine.

Example columns:

| Committee / Engine | Score | Weight | Contribution | Decision / Vote | Confidence | Evidence Status |
|---|---:|---:|---:|---|---:|---|

Possible contributors include, when declared by the strategy:

- Fundamental Analysis
- Market Intelligence
- Conviction
- Momentum
- Technical Analysis
- Market Regime
- Portfolio Risk
- Opportunity Quality
- Entry / Timing
- Capital Efficiency
- Decision Stability
- Strategy-specific committees

The dashboard must not invent a committee that the strategy did not declare.

#### Evidence Used

Show the evidence supporting each committee's decision.

Required fields when available:

- Evidence source
- Artifact or report ID
- Evidence category
- Observation or finding
- Positive, negative, or neutral impact
- Score impact
- Confidence
- Evidence timestamp
- Source freshness
- Link or path to the underlying report when safe and available

#### Decision Calculation

Show how committee scores were combined, including:

- Component score
- Weight
- Weighted contribution
- Missing-evidence treatment
- Final score
- Threshold or gate applied
- Any veto, safety, or risk rule

Opportunity Quality and Entry / Timing must remain separate when the strategy defines them separately.

#### Alternatives and Rejections

When evidence is available, show:

- Other candidates considered
- Challenger instrument
- Why this instrument ranked higher
- Why alternatives were rejected or deferred
- Replacement relationship, if any

#### AI CIO Commentary

Provide a concise explanation derived from the recorded evidence. Commentary must distinguish recorded facts from interpretation and must not claim evidence that was not supplied.

## Data Contract Requirements

Each strategy should be able to declare the following artifact roles through Registry v2:

- Portfolio / positions
- Watchlist
- Performance
- Income
- Health and readiness
- Decision journal
- Committee scores
- Decision evidence
- Opportunity quality
- Entry / timing
- Lifecycle

The dashboard must discover these artifacts from the registry rather than rely on strategy-specific hardcoded filenames.

## Completeness and Evidence Rules

- Enterprise totals include only reported numeric evidence.
- Every total reports the number of contributing strategies and the total number registered.
- Partial totals are labeled `Partial` or `Incomplete`.
- Missing evidence is displayed as `Not Reported`.
- Stale evidence is visibly identified.
- Reconstructed evidence must be labeled as reconstructed and must not be presented as authoritative strategy evidence.
- Registry-only strategies remain visible even when detailed KPI evidence is unavailable.

## Navigation and Layout

The final portal layout uses:

- Left navigation panel
- Horizontal enterprise KPI cards at the top
- Strategy selector or strategy KPI table
- One View Analysis workspace below summary cards
- Contributor tables
- Watchlist table
- Portfolio and positions table
- AI CIO Commentary panel
- Metric definition and help links

Suggested left navigation entries:

- Enterprise Overview
- Investor Dashboard
- Executive Dashboard
- Strategy Allocation
- Strategies
- Portfolio & Positions
- Watchlists
- Income
- Performance
- Risk & Health
- Decision Journal
- Evidence
- Reports
- System Status

## Acceptance Criteria

This design is implemented only when all of the following are true:

1. Enterprise KPI cards show totals across all registered strategies.
2. Every enterprise KPI card has a working `More` or `Details` drill-down.
3. Contributor tables identify each strategy's contribution and missing evidence.
4. Income includes all income categories under one enterprise total.
5. Performance, Realized P&L, Unrealized P&L, Win Rate, Yield, and Capital Appreciation support per-strategy drill-downs.
6. Individual strategy KPI views are generated dynamically from Registry v2.
7. A watchlist table is present and combines all strategy watchlists while preserving ownership.
8. Portfolio symbols and pairs are clickable.
9. The symbol / pair detail view explains why the instrument was selected.
10. The decision view displays committee scores and the evidence used by each committee.
11. Missing and partial evidence are clearly labeled.
12. No dashboard component changes trading, allocation, governance, or broker behavior.

## Deployment Verification

After DigitalOcean deployment, verify that:

- Both `DIVIDEND-001` and `SWING-001` appear without hardcoded UI entries.
- Any future registered strategy appears automatically.
- Enterprise totals match the sum of reported strategy evidence.
- `More` / `Details` views show contributors.
- Watchlist and portfolio tables populate from registry-declared artifacts.
- Clicking a symbol or pair opens its decision rationale, committee scorecard, and evidence view.
- Missing sections are treated as deployment defects and checked against this specification.
