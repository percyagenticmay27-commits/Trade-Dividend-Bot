# Daily Development Decision Log — 2026-08-01

## Purpose

This document records approved development and UI decisions made on August 1, 2026. It is shared architecture memory for the Enterprise AI CIO host and any current or future registered strategy.

Use this log during local development, code review, testing, DigitalOcean deployment, and missing-feature investigations. A feature documented here but absent in deployment is a deployment or implementation defect unless a later dated decision explicitly supersedes it.

## Decision Entry Standard

Each decision includes:

- Decision ID
- Date
- Phase
- Category
- Status
- Decision
- Reason
- Implementation location
- UI or reporting impact
- Tests or validation
- Deployment verification
- Related specification or image

---

## DEC-2026-08-01-001 — Canonical Registry Discovery for All Dashboard Consumers

**Date:** 2026-08-01  
**Phase:** Phase 2 — Registry Consumer Integration  
**Category:** Architecture / Registry / Dashboard  
**Status:** Implemented and focused tests passed

### Decision

The Executive Dashboard, Investor Dashboard, Enterprise Strategy KPI artifact, and dashboard refresh summary must receive the same canonical `strategy_discovery` document.

The current registered strategy IDs are:

- `DIVIDEND-001`
- `SWING-001`

### Reason

One authoritative discovery object prevents the dashboards from disagreeing about which strategies exist or reporting different status and safety metadata.

### Implementation Location

- `src/dividend_bot/enterprise_strategy_discovery.py`
- `src/dividend_bot/enterprise_dashboard_strategy_discovery.py`
- `src/dividend_bot/enterprise_strategy_kpi_adapter.py`
- `refresh_enterprise_dashboards.py`

### Tests / Validation

- `tests/test_enterprise_strategy_discovery.py`
- `tests/test_enterprise_dashboard_strategy_discovery.py`
- `tests/test_refresh_dashboard_strategy_discovery_integration.py`

### Deployment Verification

All generated dashboard artifacts must show both registered strategy IDs without hardcoded UI entries.

---

## DEC-2026-08-01-002 — Investor Dashboard Is the Enterprise-Level Summary

**Date:** 2026-08-01  
**Phase:** Phase 3 / UI Specification  
**Category:** Investor Dashboard / Reporting  
**Status:** Approved and documented

### Decision

The Investor Dashboard is the high-level consolidated view across all registered strategies. Enterprise cards show totals only from strategies that reported compatible evidence.

Required enterprise metrics include:

- Portfolio Value
- Allocated Capital
- Available Cash / Reserve
- Income
- Performance
- Realized P&L
- Unrealized P&L
- Win Rate
- Yield
- Capital Appreciation
- Enterprise Health
- High-level watchlist counts when supported

### More / Details Rule

Income, Performance, Realized P&L, Unrealized P&L, Win Rate, Yield, and Capital Appreciation each require a `More` or `Details` action. The detail workspace shows every strategy's contribution or `Not Reported` status.

Missing evidence must not be silently converted to zero. Partial totals must state how many registered strategies contributed.

### Related Specification

- `docs/ENTERPRISE_INVESTOR_DASHBOARD_UI_SPEC_V1.md`

### Deployment Verification

Each required enterprise card and its contributor drill-down must be visible and functional after DigitalOcean deployment.

---

## DEC-2026-08-01-003 — Strategy KPI Workspaces Contain Only Their Own Strategy Data

**Date:** 2026-08-01  
**Phase:** Phase 3 / UI Specification  
**Category:** Strategy KPI / Dashboard Boundaries  
**Status:** Approved and documented

### Decision

A strategy KPI workspace must show only the selected strategy's own data. It must not mix other strategies' portfolio, watchlist, analytics, performance, income, P&L, or decision evidence into that workspace.

Current implementation scope:

- Dividend KPI workspace
- Swing KPI workspace

Future Options and Futures strategies will receive their own KPI workspaces later, but they do not block the current Dividend and Swing implementation.

### Dividend KPI Scope

Only Dividend strategy data, including its own:

- Portfolio and holdings
- Watchlist
- Income and payments
- Performance
- Realized and unrealized P&L
- Health, readiness, and evidence
- Decision rationale

### Swing KPI Scope

Only Swing strategy data, including its own:

- Portfolio and positions
- Watchlist
- Performance
- Realized and unrealized P&L
- Win rate
- Opportunity Quality
- Entry / Timing score
- Health, readiness, and evidence
- Decision rationale

### Deployment Verification

Selecting Dividend must never show Swing-owned rows, and selecting Swing must never show Dividend-owned rows.

---

## DEC-2026-08-01-004 — Watchlists Remain Strategy-Owned

**Date:** 2026-08-01  
**Phase:** Phase 3 / UI Specification  
**Category:** Watchlist / KPI  
**Status:** Approved and documented

### Decision

Each strategy KPI workspace contains its own watchlist table only.

The Investor Dashboard may show high-level watchlist counts, such as Dividend Watchlist Count and Swing Watchlist Count. Its `More/Details` view may list symbols grouped by owning strategy.

A combined watchlist table must not be placed inside the Income detail section.

### Deployment Verification

- Dividend KPI shows only Dividend watchlist candidates.
- Swing KPI shows only Swing watchlist candidates.
- Enterprise watchlist counts preserve strategy ownership.

---

## DEC-2026-08-01-005 — Clickable Instrument Decision Analysis

**Date:** 2026-08-01  
**Phase:** Phase 4 planning / UI Specification  
**Category:** Portfolio / Decision Evidence / One View Analysis  
**Status:** Approved and documented; implementation pending

### Decision

Clicking a stock, ETF, pair, option, future, or other instrument in a strategy's portfolio or position table opens a strategy-specific `More/Details` One View Decision Analysis.

The detail must show, when supplied by the owning strategy:

- Why the instrument was selected
- Contribution to strategy and enterprise income
- Contribution to strategy and enterprise performance
- Realized and unrealized P&L
- Win/loss information
- Every participating committee or engine
- Committee score, weight, weighted contribution, vote, and confidence
- Evidence used by each committee
- Evidence timestamps and freshness
- Final score and thresholds
- Gates, vetoes, and risk rules
- Alternatives, challengers, and rejected candidates
- AI CIO commentary distinguishing recorded facts from interpretation

Opportunity Quality and Entry / Timing remain separate measures when the strategy defines them separately.

### Related Specification

- `docs/ENTERPRISE_INVESTOR_DASHBOARD_UI_SPEC_V1.md`

### Deployment Verification

Clicking an instrument must open the recorded decision rationale and evidence rather than a generic or empty details panel.

---

## DEC-2026-08-01-006 — Phase 3 AI CIO Interpretation Is Read-Only

**Date:** 2026-08-01  
**Phase:** Phase 3.1  
**Category:** AI CIO / Interpretation  
**Status:** Implemented and focused tests passed

### Decision

The AI CIO multi-strategy interpretation layer may aggregate and explain evidence but must not:

- Recommend allocation changes
- Move cash or capital
- Place or prepare broker orders
- Modify strategy calculations
- Invent missing evidence

### Implementation Location

- `src/dividend_bot/enterprise_ai_cio_strategy_interpretation.py`
- `tests/test_enterprise_ai_cio_strategy_interpretation.py`

### Evidence Rule

Enterprise totals include contributor counts and completeness. Missing per-strategy evidence remains `None` / `Not Reported`.

---

## DEC-2026-08-01-007 — Phase 3.2 Enterprise Strategy Comparison Engine

**Date:** 2026-08-01  
**Phase:** Phase 3.2  
**Category:** AI CIO / Comparison / Reporting  
**Status:** Implemented; local tests pending user execution

### Decision

The comparison engine compares only values already published by the AI CIO interpretation document. It identifies evidence-based leaders, contributor shares, differences, status distributions, missing evidence, and completeness.

It must not generate recommendations or allocation changes.

### Initial Comparison Metrics

- Allocated Capital
- Portfolio Value
- Realized P&L
- Unrealized P&L
- Income
- Watchlist Count
- Position Count
- Opportunity Quality
- Win Rate
- Runtime Status
- Health Status
- Readiness
- Evidence Status

### Comparison Policy

- Ranking basis: reported evidence only
- Missing evidence: `Not Reported`
- Enterprise totals: reported values only
- Pairwise differences preserve direction
- Deterministic ordering by strategy ID
- No recommendation generation
- No allocation change generation

### Implementation Location

- `src/dividend_bot/enterprise_strategy_comparison_engine.py`
- `tests/test_enterprise_strategy_comparison_engine.py`

### Deployment Verification

The AI CIO must be able to explain, using supplied evidence, which currently registered strategy leads each comparable metric and whether the comparison is complete or partial.

---

## Image and Screenshot Record

Screenshots discussed during this development session were provided in the ChatGPT project conversation and used to validate:

- Registry discovery failures and fixes
- Canonical discovery payload consistency
- Phase 2 focused test results
- Phase 3 interpretation test results
- Investor and strategy KPI design boundaries

Repository image copies have not yet been committed. When screenshots are exported into the repository, place them under:

```text
docs/decisions/2026/08/images/
```

and add their exact filenames and related Decision IDs to this section.

---

## Daily Status Summary

### Implemented

- Canonical registry discovery across dashboard consumers
- Registry-driven KPI adapter
- Dashboard refresh discovery integration
- AI CIO multi-strategy interpretation adapter
- Enterprise strategy comparison engine

### Approved and Documented

- Investor Dashboard enterprise totals and contributor drill-downs
- Strategy-only KPI workspace boundaries
- Strategy-owned watchlists
- Clickable instrument committee evidence and decision analysis
- Current focus on Dividend and Swing

### Next Development Units

1. Run focused tests for the Enterprise Strategy Comparison Engine.
2. Build the Enterprise Contributor Engine powering Investor Dashboard `More/Details` tables.
3. Publish interpretation and comparison artifacts through the dashboard refresh process.
4. Build Dividend and Swing strategy KPI provider contracts.
5. Implement strategy-owned watchlist and portfolio evidence adapters.
6. Implement One View Decision Analysis after the evidence contracts are complete.
