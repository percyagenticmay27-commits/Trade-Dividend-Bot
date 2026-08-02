# Phase 6.3 — Real Unified Dashboard Cycle Acceptance

## Decision

Phase 6.3 adds a production-safe acceptance gate around the Phase 6.2 unified
dashboard cycle. The gate executes the real reporting pipeline and accepts it
only when the cycle passes, all required artifacts exist and are readable, all
safety fields remain locked, and the protected state directory is unchanged.

## Acceptance evidence

- SHA-256 manifest, size, and path for each required artifact.
- Before/after SHA-256 manifests for protected runtime state.
- Cycle and acceptance pass/fail status.
- Consolidated warnings and errors.
- Deterministic JSON and Markdown acceptance reports.

## Safety boundary

- Paper trading only.
- No Robinhood or other broker connection.
- No order placement or capital movement.
- No changes to strategy calculations, KPI Contract v1.0, allocations,
  governance, cash, registry, or runtime state.

## Outputs

- `results/enterprise_unified_dashboard_cycle_acceptance.json`
- `results/enterprise_unified_dashboard_cycle_acceptance.md`
