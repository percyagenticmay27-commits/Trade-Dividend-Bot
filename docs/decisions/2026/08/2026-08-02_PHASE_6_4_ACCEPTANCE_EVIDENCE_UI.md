# Phase 6.4 — Unified Dashboard Acceptance Evidence UI

## Decision

Phase 6.4 publishes the real Phase 6.3 acceptance evidence as a standalone,
operator-readable HTML report. The page independently cross-checks acceptance,
cycle, and validation status before displaying a verification result.

## Visible evidence

- Acceptance, cycle, and validation status.
- Protected-state immutability result.
- Separate Dividend and Swing KPI validation rows.
- Artifact sizes and SHA-256 integrity evidence.
- Consolidated warnings and errors.

## Safety boundary

The renderer is paper-only, read-only, script-free, and reporting-only. Artifact
links are restricted to local filenames. Untrusted evidence is HTML escaped. It
does not change strategies, calculations, allocations, governance, registry,
cash, runtime state, or Enterprise KPI Contract v1.0.

## Output

- `results/enterprise-unified-dashboard-acceptance.html`
