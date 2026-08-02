# Phase 4.2 Decision Journal Generators — Decision Log

**Date:** 2026-08-01  
**Status:** Implemented; local validation pending

## Decision

The Enterprise portal refresh must always publish strategy-scoped Decision Journal JSON artifacts for the current Dividend and Swing strategies.

## Required Outputs

- `results/dividend_strategy_decision_journal.json`
- `results/swing_strategy_decision_journal.json`

## Evidence Rule

The generator must never invent a decision. It may read compatible strategy-owned decision source records. When no compatible source exists, it publishes a valid empty journal with `evidence_status: NOT_REPORTED` and an explanatory warning.

## Strategy Scope

- Dividend output accepts only `DIVIDEND-001` records and validates ecosystem-pair or explicitly self-funded decision structures.
- Swing output accepts only `SWING-001` records and validates individual Swing opportunity decisions.
- Cross-strategy records are filtered before contract validation.
- Entries are sorted newest first.

## Portal Integration

`refresh_enterprise_portal.py` runs in this order:

1. Base Enterprise dashboard refresh
2. Phase 3 intelligence publication
3. Dividend and Swing Decision Journal generation

The journal paths are included in the combined portal refresh summary.

## Safety

- Paper only
- Read only
- No broker execution
- No capital movement
- Atomic JSON writes

## Validation

Focused tests:

- `tests/test_strategy_decision_journal_generator.py`
- `tests/test_refresh_enterprise_portal.py`

## Deployment Verification

After portal refresh, both journal JSON files must exist. Empty evidence is acceptable only when clearly labeled `NOT_REPORTED`; it must not be represented as a fabricated decision or numeric zero.
