# Swing Realized Income UI Compatibility Addendum

## Purpose

Document the Enterprise UI evidence contract introduced by the Dividend realized-income milestone so SWING-001 can display comparable income fields when applicable without copying Dividend-specific business logic.

## Enterprise-normalized realized income fields

A strategy may publish:

- `gross_distribution_income`
- `income_adjustments`
- `net_income_received`
- `realized_income_event_count`
- `positive_income_event_count`
- `negative_income_event_count`
- `income_accounting_method`
- `income_evidence_source`
- `income_events[]`

Each realized income event should provide, when authoritative:

- `date`
- `symbol`
- `event_type`
- `amount`
- `source`

## Semantic requirements

`net_income_received` is realized strategy income only. It must not include realized stock-trade gain/loss, unrealized P&L, proceeds from a sale, capital transfers, or allocation changes.

Positive values represent realized income receipts. Negative values represent explicit strategy-owned reversals, corrections, or income adjustments. Missing evidence must remain unreported rather than inferred.

## Swing-specific rule

SWING-001 should publish these fields only when the Swing strategy actually has income-producing events that fit this contract. A Swing capital gain or loss is performance evidence, not income evidence.

If Swing has no applicable realized income source, it may publish zero only when its authoritative ledger proves zero realized income for the covered period; otherwise it should report the field as unavailable/not reported according to the Enterprise contract.

## UI behavior

The shared Enterprise Income workspace may display:

- Net Income Received
- Gross Distributions
- Income Adjustments
- Projected Annual Income
- Projected Monthly Income
- Income-Producing Positions
- Distribution History

The UI remains read-only and must not create, reverse, or mutate strategy transactions.
