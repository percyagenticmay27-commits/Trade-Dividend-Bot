# Phase 6.5 — Complete Acceptance Evidence Package

## Decision

Phase 6.5 runs the real Phase 6.3 acceptance gate, verifies the Phase 6.4
operator evidence page, and packages the complete accepted artifact set into one
deterministic ZIP archive.

## Package integrity

- Every artifact is named explicitly and must be a flat local filename.
- Every artifact is nonempty and hashed with SHA-256 before packaging.
- Each file is hashed again immediately before it enters the archive.
- ZIP timestamps and permissions are fixed so identical inputs create identical
  package hashes.
- The package contains its own JSON artifact manifest.

## Fail-closed behavior

Failed acceptance, failed UI verification, missing artifacts, changed artifacts,
or unsafe paths prevent a passing package.

## Safety boundary

The package is paper-only and reporting-only. It does not connect to Robinhood
or another broker, place orders, move capital, or change strategies,
calculations, allocations, governance, registry, cash, protected runtime state,
or Enterprise KPI Contract v1.0.

## Outputs

- `results/enterprise-unified-dashboard-evidence-package.zip`
- `results/enterprise_unified_dashboard_evidence_package.json`
- `results/enterprise_unified_dashboard_evidence_package.md`
