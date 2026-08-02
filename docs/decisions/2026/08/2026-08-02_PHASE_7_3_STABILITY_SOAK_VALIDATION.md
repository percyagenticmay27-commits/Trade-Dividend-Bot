# Phase 7.3 — Long-Duration Stability and Soak Validation

## Decision

Phase 7.3 records one compact operational sample per scheduled server run and
validates stability across time. It does not sleep, block the scheduler, rerun
trading logic, or copy secrets.

## Completion contract

- At least 7 unique samples.
- At least 168 elapsed hours.
- No sampling gap greater than 36 hours.
- Evidence package, acceptance, UI verification, recovery, and restore statuses
  pass on every sample.
- Production hardening remains `READY` or `READY_WITH_WARNINGS`.
- Paper-only safety fields remain locked on every sample.

Insufficient evidence is `IN_PROGRESS`, not a failure. Any failed status,
unsafe field, malformed timestamp, duplicate timestamp, or excessive completed
sampling gap is `FAILED`.

## Safety boundary

The soak validator is paper-only and reporting-only. It does not connect to
Robinhood or another broker, place orders, move capital, expose environment
values, or change strategies, calculations, allocations, governance, registry,
cash, or runtime state.

## Outputs

- `results/enterprise_stability_soak_samples.jsonl`
- `results/enterprise_stability_soak_validation.json`
- `results/enterprise_stability_soak_validation.md`
