# Phase 5.1 Executive Dashboard Decision Journal Integration

Date: 2026-08-01

## Accepted decision

The Enterprise Executive and Investor dashboards will load the Decision Journal through a strategy-scoped adapter. The selected KPI workspace determines which journal artifact is loaded.

- Dividend KPI loads only `dividend_strategy_decision_journal.json`.
- Swing KPI loads only `swing_strategy_decision_journal.json`.
- Cross-strategy artifacts are rejected.
- Missing artifacts return a safe empty Decision Journal tab instead of breaking the portal.
- Decision entries remain newest first.
- The adapter reuses the validated Decision Journal renderer rather than duplicating display logic.

## Approved KPI tabs

1. Executive Summary
2. Portfolio
3. Watchlist
4. Income
5. Alerts
6. Decision Journal

Performance remains summarized in Executive Summary. Holdings remains part of Portfolio.

## Safety

The integration is paper-only, read-only, and cannot execute trades, move capital, or call a broker.

## Implementation

- `src/dividend_bot/enterprise_decision_journal_adapter.py`
- `tests/test_enterprise_decision_journal_adapter.py`

## Next unit

Embed the adapter output into the scan-first KPI workspace and add tab switching so the selected strategy's Decision Journal appears inside the approved Enterprise page layout.
