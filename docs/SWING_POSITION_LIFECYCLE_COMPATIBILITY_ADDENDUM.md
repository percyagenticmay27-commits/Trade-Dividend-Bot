# Swing Position Lifecycle Compatibility Addendum

## Purpose

This addendum records the Enterprise position-lifecycle evidence introduced during the Dividend KPI aggregation restoration milestone. It is guidance for the Swing repository only; no Swing repository code is changed here.

## Enterprise lifecycle contract

A strategy may publish current holdings separately from historical lifecycle evidence. Historical positions must never be reintroduced into the current holdings collection merely because they exist in a trade ledger.

Normalized lifecycle statuses supported by the Enterprise presentation layer are:

- `OPEN` — currently held and no prior full exit precedes the current open lot.
- `REENTERED` — currently held after a prior full exit and later new entry.
- `PARKED_IN_SGOV` — exited from the strategy position and proceeds were parked in the reserve/cash vehicle.
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
- `last_exit_value` when the strategy ledger publishes an authoritative exit or parked value
- `pair` or strategy grouping when applicable
- `sleeve` when applicable
- `reentry_count`
- `event_count`
- `evidence_source`

## Current holdings contract

Current holding rows may additionally carry:

- `lifecycle_status`
- `lifecycle_first_purchase_date`
- `lifecycle_current_open_date`
- `lifecycle_last_exit_date`
- `lifecycle_reentry_count`
- `lifecycle_evidence_source`

Historical lifecycle rows are reporting evidence only and must not increase current position count, portfolio market value, or deployed capital.

## Position / Sales History presentation contract

The Enterprise Performance workspace now supports a separate `Position / Sales History` presentation sourced from lifecycle evidence. Swing can participate by publishing the normalized lifecycle fields above through its own authoritative artifacts.

The history view is separate from:

- current holdings;
- dividend/distribution history;
- realized income accounting;
- watchlist candidates.

Recommended presentation columns are:

- Symbol
- Strategy grouping/pair when applicable
- Sleeve when applicable
- Lifecycle Status
- Purchase Date
- Exit Date
- Exit Action
- Exit/Parked Value when authoritative
- Re-entry Count
- Evidence Source

Swing must not publish a Dividend-specific `PARKED_IN_SGOV` state unless Swing actually uses SGOV as its reserve mechanism. If Swing uses another cash or reserve mechanism, preserve the native lifecycle meaning and map it to the Enterprise reporting contract without changing Swing calculations.

## Legacy parking-row compatibility

The Dividend implementation encountered legacy paper-ledger rows where a reserve transfer row used `Ticker=SGOV` while the original position identity was represented by `Pair` plus `Sleeve`. The Dividend host normalizes those rows back to the source position for historical reporting. Swing should only implement an equivalent normalization if its own historical artifacts have an analogous representation.

## Swing implementation guidance

Swing should derive lifecycle from its own authoritative execution/paper lifecycle artifacts. Do not copy Dividend-specific pair or SGOV assumptions unless the Swing strategy actually uses them. If Swing parks capital in another reserve mechanism, map that reserve state to the Enterprise lifecycle contract without changing Swing strategy calculations.

The Swing Enterprise plugin should eventually expose lifecycle evidence alongside its holdings/positions artifacts so the AI CIO can distinguish current positions from closed and re-entered opportunities.

## Safety

This contract is read-only and reporting-only. It must not enable live trading, broker execution, order placement, or automatic capital movement.
