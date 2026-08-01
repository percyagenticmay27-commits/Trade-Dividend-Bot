# Phase 4 Scan-First Enterprise Dashboard Decision Log

**Date:** 2026-08-01  
**Status:** Approved for staging implementation  
**Scope:** Enterprise Executive Summary, Investor Summary, and strategy KPI navigation

## Decision ID

`DEC-2026-08-01-P4-SCAN-FIRST-001`

## Problem observed

The first Enterprise staging preview successfully rendered without runtime errors, but the layout was too dense and technical. Registry identity, capabilities, artifact contracts, evidence paths, health summaries, runtime summaries, and strategy data competed for attention on the same screen.

An investor could not immediately answer the primary questions:

1. Is the enterprise profitable or losing money?
2. Is the system working well or does it need immediate attention?
3. Which strategy is contributing most positively?
4. Which strategy needs the most concern?
5. Which stock, ETF, pair, ecosystem, option, or contract inside that strategy is responsible?

## Approved information hierarchy

The Enterprise portal must be organized for rapid top-to-bottom scanning.

### Level 1 — Enterprise condition

The first visible row must show:

- Profit / Loss
- Portfolio Value
- Projected Income
- Overall Health
- Action Needed

The page must not require the investor to inspect registry metadata to determine whether the system is profitable, healthy, or in need of attention.

### Level 2 — Priority concern

The page must clearly identify:

- highest-concern strategy;
- reason for concern;
- whether immediate action, priority review, or continued monitoring is appropriate.

A strategy may be elevated by negative P&L, degraded health, non-running runtime, or incomplete evidence.

### Level 3 — Strategy comparison

Registered strategies must be shown as scan-friendly cards ordered by concern.

Each card shows only the information necessary to decide whether to inspect it:

- strategy name;
- reported P&L or `Not reported`;
- health;
- main concern reason;
- `View strategy KPI` action.

### Level 4 — Strategy KPI workspace

After selecting a strategy, the KPI workspace must contain only that strategy's data:

- allocated capital;
- portfolio value;
- income;
- realized P&L;
- unrealized P&L;
- win rate;
- watchlist count;
- positions or holdings count;
- Opportunity Quality;
- evidence readiness.

The KPI workspace remains the path to that strategy's own portfolio, watchlist, analytics, performance, and evidence.

### Level 5 — Instrument analysis

The next Phase 4 unit will allow the investor to select a stock, ETF, pair, ecosystem, option, future, or other instrument and inspect:

- performance contribution;
- enterprise and strategy income contribution;
- realized and unrealized P&L contribution;
- win/loss history;
- committee scores;
- weighted contributions;
- evidence used by each committee;
- final decision reason;
- risks, gates, vetoes, challengers, and alternatives.

## Technical metadata placement

The following information must remain available but must not dominate the main investor view:

- registry identity;
- declared capabilities;
- published artifact contract;
- raw evidence paths;
- deployment diagnostics;
- schema and contract metadata.

These items belong in collapsed diagnostic sections or dedicated technical pages.

## Layout decision

The main page remains a top-to-bottom page, not a collection of overlapping content tabs.

The top preview navigation may switch between Executive Summary and Investor Summary, but each page follows the same scan hierarchy.

## Safety rules

The UI remains:

- paper-only;
- read-only;
- reporting-only;
- no broker execution;
- no capital movement;
- no live trading.

Missing evidence must display as `Not reported`, not zero.

## Implementation

Created:

- `src/dividend_bot/enterprise_scan_first_ui.py`

Updated:

- `generate_enterprise_preview.py`
- `tests/test_generate_enterprise_preview.py`

Generated staging artifacts remain:

- `results/enterprise-preview.html`
- `results/enterprise-preview-status.json`

Recommended staging route remains:

- `/enterprise-preview`

## Deployment validation

After deployment to DigitalOcean, verify that the first screen allows an investor to identify within a few seconds:

- whether reported performance is positive, negative, break-even, or incomplete;
- enterprise health;
- required action level;
- highest-concern strategy;
- strategy KPI navigation.

A deployment that returns to the dense registry-first layout is considered a UI regression against this decision.
