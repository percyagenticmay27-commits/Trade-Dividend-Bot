# Phase 5.5 Enterprise Cross-Linking

**Date:** 2026-08-02  
**Status:** Implemented; local validation pending

## Decision

The Executive Dashboard, Investor Dashboard, selected strategy KPI workspace,
and strategy Decision Journal are connected with stable strategy-aware links.

## URL contract

- `strategy=<strategy_id>` selects the requested registered strategy.
- `tab=<tab_id>` selects a KPI workspace tab.
- `#strategy-<strategy_id>` provides a stable workspace anchor.
- Missing tab state defaults to `executive-summary`.
- Decision Journal links request `tab=decisions`.

## Behavior

Both Enterprise dashboards restore the selected strategy and requested tab from
the URL. Every strategy workspace exposes links to the Executive Dashboard,
Investor Dashboard, its own workspace, and its Decisions view. Standalone and
embedded journals link back to the same strategy-scoped portal views.

## Strategy isolation

Cross-links carry only the selected stable strategy ID. They do not merge
evidence, alter dashboard data, or bypass Phase 5.1 journal matching. Unknown
strategy IDs are ignored by the client-side selection logic.

## Safety and compatibility

- Paper trading only
- Read-only navigation
- No Robinhood or brokerage communication
- No order placement or capital movement
- No dashboard calculation changes
- No canonical journal schema changes
- Enterprise KPI Contract v1.0 preserved
