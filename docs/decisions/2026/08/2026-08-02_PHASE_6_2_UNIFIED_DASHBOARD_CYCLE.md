# Phase 6.2 — Unified Dashboard End-to-End Cycle

## Decision

The Enterprise AI CIO now has one reporting-only cycle that generates strategy
Decision Journals, refreshes dashboard and KPI artifacts, and runs the Phase 6.1
unified validation in that order.

The cycle fails closed. A failed generation step prevents dashboard refresh, and
a failed refresh prevents validation from certifying stale artifacts. Every step
publishes status, paths, warnings, and errors in JSON and Markdown summaries.

## Safety boundary

- Paper trading only.
- No Robinhood or broker connection.
- No order placement or capital movement.
- Existing registry, allocation, cash, governance, and strategy calculations are
  read as inputs and are not mutated by the orchestrator.
- Enterprise KPI Contract v1.0 remains compatible.

## Outputs

- `results/enterprise_unified_dashboard_cycle.json`
- `results/enterprise_unified_dashboard_cycle.md`

## Verification

The focused suite covers ordered execution, path normalization, fail-closed
behavior, validation failure propagation, output generation, CLI exit codes, and
paper-only safety flags.
