# Enterprise Investor Dashboard UI Specification v1.1

## Purpose

This document is the authoritative design specification for the Enterprise Investor Dashboard and its individual strategy KPI workspaces.

It exists so the intended behavior can be verified during development, testing, and DigitalOcean deployment. If a required section is missing, empty, renamed, combined incorrectly, or rendered with the wrong scope, this document defines what was supposed to be implemented.

The dashboard remains reporting-only and paper-only. It must not place trades, move capital, alter allocations, or override strategy decisions.

## Current Implementation Scope

The current implementation scope is limited to:

- `DIVIDEND-001`
- `SWING-001`

Options, Futures, and other future strategies must eventually receive their own strategy KPI workspaces, but their detailed UI is deferred. The architecture must remain registry-driven so future strategies can be added without redesigning the enterprise summary.

## Core Separation Rule

The Investor Dashboard has two distinct layers that must never be mixed.

### Layer 1 — Enterprise Summary

The Enterprise Summary answers:

> How is the complete investment enterprise performing across all registered strategies?

It contains totals across all strategies and high-level counts. Each enterprise total includes a `More` or `Details` action that shows which strategies contributed to that total.

### Layer 2 — Individual Strategy KPI Workspace

A strategy KPI workspace answers:

> What is happening inside this one strategy?

Each KPI workspace shows only the selected strategy's own data:

- watchlist
- analytics
- portfolio or positions
- performance
- income
- realized and unrealized P&L
- win rate
- strategy health
- decision evidence

A Dividend KPI workspace must not display Swing values. A Swing KPI workspace must not display Dividend values. Future Options or Futures KPI workspaces must likewise display only their own strategy data.

## Enterprise Summary KPI Cards

The enterprise summary contains high-level totals across all registered strategies that reported compatible evidence.

Every enterprise KPI card must show:

- Dollar amount first when monetary.
- Percentage second when applicable.
- Reporting completeness when incomplete.
- A `More` or `Details` action.
- Missing evidence as `Not Reported`, never as an invented zero.

### Income

`Income` is one enterprise total covering all compatible income categories reported by the strategies.

For the present scope, this can include:

- Dividend strategy income
- Swing strategy income, when the Swing strategy reports income

Future option premium, interest, fixed-income distributions, and other income types will contribute to this same enterprise Income total rather than requiring separate enterprise cards.

`More` or `Details` shows each strategy's contribution:

| Strategy | Income Amount | Contribution % | Income Category | Reporting Period | Evidence Status |
|---|---:|---:|---|---|---|

### Performance

`Performance` is the approved enterprise-level total or normalized result across all strategies that report compatible performance evidence.

`More` or `Details` shows each strategy's own performance result and contribution:

| Strategy | Native Performance Metric | Native Value | Normalized Contribution | Reporting Period | Evidence Status |
|---|---|---:|---:|---|---|

### Realized P&L

Total realized profit and loss across all reporting strategies.

`More` or `Details` shows realized P&L by strategy.

### Unrealized P&L

Total unrealized profit and loss across all reporting strategies.

`More` or `Details` shows unrealized P&L by strategy.

### Win Rate

Enterprise win rate based on compatible completed-decision or closed-trade evidence.

It must use the approved weighted calculation based on wins and completed observations rather than a simple average of percentages whenever the required counts exist.

`More` or `Details` shows:

| Strategy | Wins | Losses | Completed Observations | Win Rate | Evidence Status |
|---|---:|---:|---:|---:|---|

### Yield

Enterprise yield across strategies that publish compatible yield evidence.

`More` or `Details` shows each contributing strategy's yield, invested value, calculation basis, and evidence completeness.

### Capital Appreciation

Total capital appreciation across all reporting strategies.

`More` or `Details` shows each strategy's capital-appreciation contribution.

### Portfolio Value

Combined current portfolio value across all reporting strategies.

`More` or `Details` shows portfolio value by strategy.

### Allocated Capital

Total paper capital allocated to all registered strategies.

`More` or `Details` shows each strategy's allocated amount and percentage of enterprise allocated capital.

### Available Cash / Reserve

Enterprise-level unassigned paper cash and reserve.

`More` or `Details` distinguishes centrally held reserve from strategy-retained cash when the evidence contract supports that distinction.

### Watchlist Summary

The enterprise layer may show high-level watchlist counts only.

Examples:

- Total Watchlist Count
- Dividend Watchlist Count
- Swing Watchlist Count

`More` or `Details` opens a contributor view showing the count and list of symbols, pairs, or ecosystems grouped by strategy.

The enterprise summary does not replace the strategy-specific watchlist tables.

## Enterprise More / Details Standard

Each enterprise KPI card uses the same One View Analysis pattern.

The selected metric opens a workspace below the cards containing:

- What is this?
- How is it calculated?
- Why does it matter?
- Is this estimated?
- Measurement period
- Strategy contributor table
- Evidence completeness
- AI CIO commentary

The contributor table lists every registered strategy, including strategies with missing evidence.

## Individual Strategy KPI Workspaces

Each registered strategy receives its own KPI workspace generated from Registry v2.

A strategy KPI workspace displays only evidence owned by that strategy.

### Common Strategy KPI Areas

When available, each strategy workspace shows:

- Strategy name and ID
- Strategy type and class
- Lifecycle status
- Runtime status
- Health and readiness
- Evidence freshness
- Allocated capital
- Portfolio value
- Realized P&L
- Unrealized P&L
- Income
- Return or native performance measure
- Win rate
- Position count
- Watchlist count
- Opportunity Quality or equivalent strategy score

### Dividend Strategy KPI Workspace

The Dividend KPI displays only Dividend strategy evidence, including:

- Dividend watchlist
- Dividend portfolio holdings
- Dividend income
- Current yield
- Projected annual income
- Payment reliability
- Upcoming payments
- Dividend strategy performance
- Realized and unrealized P&L
- Dividend decision evidence

### Swing Strategy KPI Workspace

The Swing KPI displays only Swing strategy evidence, including:

- Swing watchlist
- Swing portfolio or open positions
- Opportunity Quality
- Entry or timing score, kept separate from Opportunity Quality
- Watchlist promotions and demotions
- Candidate ranking
- Market regime context
- Swing strategy performance
- Realized and unrealized P&L
- Win rate
- Swing decision evidence

### Future Strategy KPI Workspaces

Options, Futures, and future strategies will require their own KPI workspaces.

Examples of future strategy-specific content include:

- Current option contracts
- Premium and income contribution
- Return and win/loss by option
- Current futures contracts
- Margin usage
- Return and drawdown by contract

These are deferred and must not delay the present Dividend and Swing implementation.

## Strategy Watchlist Table

Each strategy KPI workspace contains its own watchlist table.

There is no combined watchlist table inside an individual strategy KPI.

### Required Watchlist Columns

| Field | Description |
|---|---|
| Symbol / Pair / Ecosystem | Strategy-owned candidate identifier |
| Instrument Type | Equity, ETF, pair, option, future, or other type |
| Watchlist Status | Candidate, monitoring, promoted, demoted, rejected, pending, or normalized strategy status |
| Opportunity / Quality Score | Strategy's approved quality measure |
| Entry / Timing Score | Separate timing measure when published |
| Conviction | Strategy conviction score or classification |
| Risk | Risk score or principal risk flag |
| Market Regime | Regime context used by the strategy |
| Added Date | Date added to this strategy's watchlist |
| Last Updated | Evidence freshness timestamp |
| Details | Opens the strategy-specific decision analysis |

## Strategy Portfolio or Positions Table

Each strategy KPI workspace contains only that strategy's holdings or positions.

### Required Columns

| Field | Description |
|---|---|
| Symbol / Pair / Contract | Clickable strategy-owned instrument |
| Instrument Type | Equity, ETF, pair, option, future, or other type |
| Quantity / Contracts | Position quantity or contract count |
| Cost Basis | Reported cost basis |
| Market Value | Current paper market value |
| Allocation | Dollar amount first, percentage second |
| Income Contribution | Amount this instrument contributes to the strategy's income and enterprise Income total |
| Realized P&L | Realized result for this instrument |
| Unrealized P&L | Current unrealized result |
| Win / Loss Status | Closed result or current strategy-defined status when available |
| Lifecycle Status | Active, monitoring, protected, pending, replaced, closed, or normalized state |
| Health / Risk | Position health and principal risk status |
| Last Updated | Evidence timestamp |
| Details | Opens the strategy-specific decision analysis |

## Clickable Instrument Details

Selecting a stock, ETF, pair, option contract, futures contract, or other strategy instrument opens a One View Decision Analysis for that instrument.

The detail belongs to the selected strategy only.

### Required Instrument Detail Sections

#### Contribution Summary

Show the instrument's contribution to:

- Strategy portfolio value
- Enterprise portfolio value, when calculable
- Strategy income
- Enterprise Income total
- Strategy realized P&L
- Strategy unrealized P&L
- Strategy win/loss results
- Strategy performance

#### Decision Summary

- Strategy name and ID
- Instrument
- Decision type
- Decision timestamp
- Current lifecycle status
- Plain-language reason the strategy selected the instrument

#### Committee Scorecard

Show every participating committee or engine declared by that strategy.

| Committee / Engine | Score | Weight | Weighted Contribution | Decision / Vote | Confidence | Evidence Status |
|---|---:|---:|---:|---|---:|---|

For the current Dividend and Swing scope, possible contributors may include:

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

The UI must not invent a committee that the selected strategy did not declare.

#### Committee Evidence

For each committee or engine, show the evidence supporting its score and decision:

- Evidence source
- Artifact or report ID
- Observation or finding
- Positive, negative, or neutral impact
- Score impact
- Confidence
- Evidence timestamp
- Freshness
- Safe path or link to the underlying report when available

#### Decision Calculation

Show:

- Component score
- Weight
- Weighted contribution
- Missing-evidence treatment
- Final score
- Threshold or gate
- Veto, safety, or risk rule

Opportunity Quality and Entry / Timing remain separate whenever the strategy defines them separately.

#### Alternatives and Rejections

When available, show:

- Other candidates considered
- Challenger instrument
- Why the selected instrument ranked higher
- Why alternatives were rejected or deferred
- Replacement relationship

#### AI CIO Commentary

Provide a concise explanation derived only from recorded evidence. It must distinguish recorded facts from interpretation.

## Registry and Artifact Requirements

For the current Dividend and Swing strategies, Registry v2 should declare the relevant artifact roles for:

- Strategy portfolio or positions
- Strategy watchlist
- Strategy performance
- Strategy income
- Strategy health and readiness
- Decision journal
- Committee scores
- Committee evidence
- Opportunity Quality
- Entry or timing
- Lifecycle

The host dashboard must discover these artifacts from the registry rather than hardcode strategy-specific filenames.

## Navigation and Layout

The final portal uses:

- Left navigation
- Horizontal enterprise KPI cards
- Enterprise One View Analysis workspace
- Strategy selector or strategy cards
- One strategy KPI workspace at a time
- Strategy-owned watchlist table
- Strategy-owned portfolio or positions table
- Clickable instrument details
- AI CIO commentary
- Metric definitions and help links

Suggested left navigation:

- Enterprise Overview
- Investor Dashboard
- Executive Dashboard
- Strategy Allocation
- Strategies
- Dividend KPI
- Swing KPI
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

This design is implemented only when:

1. Enterprise Income has a working contributor drill-down.
2. Enterprise Performance has a working contributor drill-down.
3. Enterprise Realized P&L has a working contributor drill-down.
4. Enterprise Unrealized P&L has a working contributor drill-down.
5. Enterprise Win Rate has a working contributor drill-down.
6. Enterprise Yield has a working contributor drill-down.
7. Enterprise Capital Appreciation has a working contributor drill-down.
8. Enterprise watchlist counts can drill into strategy-grouped symbol lists.
9. Dividend KPI shows only Dividend data.
10. Swing KPI shows only Swing data.
11. Each strategy KPI has its own watchlist table.
12. Each strategy KPI has its own portfolio or positions table.
13. Clicking an instrument shows its contribution, win/loss and P&L evidence, committee scores, and committee evidence.
14. Missing evidence is clearly labeled.
15. No component changes trading, allocation, governance, or broker behavior.

## Deployment Verification

After DigitalOcean deployment, verify:

- `DIVIDEND-001` and `SWING-001` appear as separate KPI workspaces.
- Dividend KPI contains no Swing rows or values.
- Swing KPI contains no Dividend rows or values.
- Enterprise KPI cards show totals across reporting strategies.
- Every required enterprise total has a working `More` or `Details` contributor view.
- Each strategy's watchlist and portfolio populate from its own registry-declared artifacts.
- Clicking a Dividend or Swing instrument opens its strategy-specific rationale, committee scorecard, evidence, and contribution details.
- Missing sections or mixed strategy data are treated as deployment defects against this specification.
