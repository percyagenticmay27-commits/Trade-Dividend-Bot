# Swing Position Lifecycle Compatibility Addendum

## Purpose

This addendum records the Enterprise position-lifecycle evidence introduced during the Dividend KPI aggregation restoration milestone. It is guidance for the Swing repository only; no Swing repository code is changed here.

## Enterprise lifecycle contract

A strategy may publish current holdings separately from historical lifecycle evidence. Historical positions must never be reintroduced into the current holdings collection merely because they exist in a trade ledger.

Normalized lifecycle statuses supported by the Enterprise presentation layer are:

- `OPEN` — currently held and no prior full exit precedes the current open lot.
- `REENTERED` — currently held after a prior full exit and later new entry.
- `PARKED_IN_SGOV` — exited from the Dividend strategy position and proceeds were parked in the reserve/cash vehicle.
- `CLOSED` — fully exited without an active current position.
- `RESERVE` — reserve capital such as SGOV; not an ordinary strategy security position.

## Recommended lifecycle fields

For each strategy-owned symbol, publish when authoritative evidence exists:

- `symbol`
- `lifecycle_status`
- `is_current_holding`
- `first_purchase_date`
- `current_open_date`
- `last_exit_date`
- `last_exit_action`
- `entry_value`
- `last_exit_value`
- `realized_gain_loss`
- `pair` or strategy grouping when applicable
- `sleeve` when applicable
- `reentry_count`
- `event_count`
- `evidence_source`

`entry_value` should represent capital committed to the most recently completed position cycle. After a full exit and later re-entry, older entry capital must not be mixed into the new cycle. `realized_gain_loss` should be computed only when authoritative entry and exit values both exist, using `last_exit_value - entry_value`; otherwise it remains not reported.

## Current holdings contract

Current holding rows may additionally carry:

- `lifecycle_status`
- `lifecycle_first_purchase_date`
- `lifecycle_current_open_date`
- `lifecycle_last_exit_date`
- `lifecycle_reentry_count`
- `lifecycle_evidence_source`

Historical lifecycle rows are reporting evidence only and must not increase current position count, portfolio market value, or deployed capital.

## Position / Sales History presentation

The Enterprise Performance workspace may render historical lifecycle evidence in a dedicated Position / Sales History table. The preferred presentation includes:

- Symbol / strategy grouping
- Sleeve when applicable
- Lifecycle status
- Entry date
- Exit date
- Entry value
- Exit value
- Realized gain/loss dollar amount
- Exit action
- Re-entry count
- Evidence source

Positive and negative realized gain/loss should be visually distinguishable. Missing transaction values must remain `Not reported`; the host must not fabricate a P&L from unrelated market-price evidence.

Distribution history remains a separate income ledger and must not contain position sales or reserve transfers.

## Swing implementation guidance

Swing should derive lifecycle from its own authoritative execution/paper lifecycle artifacts. Do not copy Dividend-specific pair or SGOV assumptions unless the Swing strategy actually uses them. If Swing parks capital in another reserve mechanism, map that reserve state to the Enterprise lifecycle contract without changing Swing strategy calculations.

The Swing Enterprise plugin should eventually expose lifecycle evidence alongside its holdings/positions artifacts so the AI CIO can distinguish current positions from closed and re-entered opportunities. Swing should publish entry value, exit value, and realized gain/loss from its own authoritative position lifecycle evidence when those values exist.

## Safety

This contract is read-only and reporting-only. It must not enable live trading, broker execution, order placement, or automatic capital movement.
