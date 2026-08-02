# Phase 5.2 Live KPI Workspace Tabs

**Date:** 2026-08-02  
**Status:** Implemented; local validation pending

## Decision

Each registered strategy receives one strategy-scoped KPI workspace with eight
live presentation tabs:

1. Executive Summary
2. Portfolio
3. Watchlist
4. Holdings
5. Income
6. Performance
7. Alerts
8. Decisions

The selected strategy controls both the visible workspace and its active tab.
Every tab is scoped by stable `strategy_id`. The Executive Summary tab is the
default active view.

## Contract behavior

The tabs render fields already supplied through Enterprise KPI Contract v1.0
and optional strategy-owned presentation fields. Missing non-applicable detail
renders an explicit empty state. Existing KPI values, calculations, registry
discovery, allocations, and Decision Journal contracts remain unchanged.

## Strategy isolation

Dividend, Swing, and future strategy workspaces do not share domain-specific
rows. Tab selection is scoped by strategy ID. Decisions continue using the
Phase 5.1 strict journal matching and cross-strategy rejection rules.

## Safety

- Paper trading only
- Read-only and reporting-only
- No Robinhood or brokerage communication
- No live orders
- No automatic capital movement
- No changes to governance or strategy calculations
- Enterprise KPI Contract v1.0 compatibility preserved
