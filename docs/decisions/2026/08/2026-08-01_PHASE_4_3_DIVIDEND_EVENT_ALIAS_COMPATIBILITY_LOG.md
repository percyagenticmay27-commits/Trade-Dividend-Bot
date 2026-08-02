# Phase 4.3 Dividend Event Alias Compatibility Decision Log

**Date:** 2026-08-01

## Problem

The strategy decision event publisher emitted the compact Dividend fields:

- `ecosystem`
- `ecosystem_node`

The Decision Journal contract expected the canonical fields:

- `ecosystem_id`
- `ecosystem_name`
- `ecosystem_mode`

This caused a valid published Dividend ecosystem-pair event to fail during journal generation with `DecisionJournalError: ecosystem_id is required`.

## Accepted Decision

Keep the publisher's new evidence model intact and add compatibility normalization at the Decision Journal boundary.

The accepted mappings are:

- `ecosystem_id` preferred; otherwise use `ecosystem`
- `ecosystem_name` preferred; otherwise use `ecosystem`, then `ecosystem_id`
- `ecosystem_mode` preferred; otherwise use `ecosystem_node`

The generated journal continues to expose only the canonical nested ecosystem schema.

## Permanent Rules

- Dividend decisions remain ecosystem decisions, not underlying-stock decisions.
- Pair decisions must still provide an income leg, leverage leg, role-specific alternatives, role-specific reasons, and pair compatibility rationale.
- Compatibility aliases must not weaken required pair evidence.
- Swing decision normalization is unchanged.
- Paper-only, read-only, and no-broker-execution rules remain unchanged.

## Files

- `src/dividend_bot/strategy_decision_journal.py`
- `tests/test_strategy_decision_journal_event_aliases.py`

## Validation

Regression coverage uses the exact compact event shape with `ecosystem: NVDA` and `ecosystem_node: PAIR`, then verifies publication, generation, and canonical journal output.
