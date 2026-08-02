# Phase 5.1 Executive Dashboard Decision Journal Integration

**Date:** 2026-08-02  
**Status:** Implemented; local validation pending

## Decision

The Enterprise Executive Dashboard consumes strategy-owned canonical Decision
Journal artifacts through a read-only Enterprise adapter. Journals are matched
strictly by `strategy_id` and attached as optional presentation data to existing
Enterprise KPI Contract v1.0 rows.

## Scope

- Load canonical `*_strategy_decision_journal.json` artifacts.
- Reject unsafe, malformed, duplicate, or cross-strategy journals.
- Preserve KPI v1.0 fields and calculations unchanged.
- Render the matching journal inside the selected strategy One View Analysis.
- Render an explicit safe empty state when a strategy has no journal evidence.
- Support nested canonical Dividend ecosystem objects.
- Preserve newest-first journal ordering and HTML escaping.

## Strategy isolation

A Dividend workspace may render only `DIVIDEND-001` decisions. A Swing
workspace may render only `SWING-001` decisions. Future strategies use the
same canonical journal contract and are matched by their own stable strategy
IDs. No strategy production code is imported by the Enterprise host.

## Safety

- Paper trading only.
- Read-only and reporting-only.
- No Robinhood or brokerage communication.
- No live orders.
- No capital movement.
- No changes to allocation, governance, strategy calculations, or KPI v1.0
  compatibility.

## Files

- `src/dividend_bot/enterprise_dashboard_decision_journal_adapter.py`
- `src/dividend_bot/enterprise_portal_strategy_ui.py`
- `src/dividend_bot/strategy_decision_journal_renderer.py`
- `refresh_enterprise_dashboards.py`
- `tests/test_enterprise_dashboard_decision_journal_adapter.py`
- `tests/test_phase_5_1_executive_dashboard_decision_journal.py`
