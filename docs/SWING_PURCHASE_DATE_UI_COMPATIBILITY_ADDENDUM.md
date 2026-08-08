# Swing Purchase Date UI Compatibility Addendum

## Purpose

The Enterprise Holdings and Income workspaces now support a normalized `purchase_date` field for currently open strategy positions.

This addendum documents what the external Swing strategy should publish so the same Enterprise UI can display the correct acquisition date for Swing positions.

## Normalized Fields

For an open position, publish when authoritative evidence exists:

- `purchase_date`
- `purchase_date_source`
- `purchase_date_method`

Recommended method value:

- `CURRENT_OPEN_POSITION_FIRST_BUY`

## Required Meaning

`purchase_date` means the date of the first acquisition belonging to the **currently open position**.

It must not mean the first time the symbol was ever traded historically.

If a position is completely closed and later re-entered, the purchase date must reset to the first acquisition date of that new open position.

Additional buys while a position remains open do not replace the original current-position purchase date.

## Missing Evidence

If Swing cannot establish the current-position acquisition date from authoritative strategy-owned lifecycle or trade evidence, publish no value. The Enterprise UI will display `Not reported`.

Do not infer or fabricate a purchase date from market data, report generation timestamps, or discovery/watchlist timestamps.

## Reserve / Cash Assets

Reserve or cash-equivalent rows should publish a purchase date only when Swing explicitly models them as acquired positions and has authoritative acquisition evidence. Otherwise leave the field unreported.

## Enterprise Presentation

When available, the Enterprise host displays Purchase Date in:

- Holdings -> Position Analytics
- Income -> Income by Holding, when the position also has income evidence

This is a presentation/evidence contract only. It does not alter strategy calculations, allocation, lifecycle rules, paper-only governance, or broker/execution locks.
