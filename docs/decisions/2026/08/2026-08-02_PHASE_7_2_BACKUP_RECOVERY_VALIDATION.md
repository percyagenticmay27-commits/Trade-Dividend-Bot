# Phase 7.2 — Backup and Recovery Validation

## Decision

Phase 7.2 adds a non-destructive recovery drill for critical paper-state and
Enterprise evidence files. The drill creates a manifest-backed backup, restores
each file only inside a temporary directory, validates size and SHA-256, removes
the temporary restore, and verifies that the live source files did not change.

## Security controls

- Absolute paths and path traversal are rejected.
- Archive members outside the snapshot scope are rejected.
- Symbolic links, hard links, directories, and other non-regular members are
  rejected.
- Archive contents must exactly match the embedded manifest.
- Restore never targets the project or deployed runtime directory.

## Safety boundary

The drill is paper-only and reporting-only. It does not run the trading cycle,
connect to Robinhood or another broker, place orders, move capital, or change
strategies, calculations, allocations, governance, registry, cash, or live
runtime state.

## Outputs

- `results/enterprise-recovery-drill.tar.gz`
- `results/enterprise_backup_recovery_validation.json`
- `results/enterprise_backup_recovery_validation.md`
