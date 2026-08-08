# Swing Enterprise Income UI Compatibility Addendum

## Purpose

The Enterprise host now renders a professional strategy-scoped Income workspace. The host owns presentation; each strategy owns its own evidence.

## Dividend Income Contract

The Dividend strategy may publish:

- `income` — realized/received paper income only.
- `projected_annual_income` — current annualized income projection from authoritative strategy evidence.
- `income_events[]` — realized strategy-owned income events.
- `holdings[].yearly_distribution_yield_percent`
- `holdings[].annual_income`
- `holdings[].payment_frequency`
- `holdings[].next_ex_dividend_date`
- `holdings[].income_analytics_source`

Projected income must remain distinct from realized income.

## Swing Requirements

Swing must **not** copy Dividend-specific distribution logic. The Swing strategy should publish income fields only when they are meaningful and authoritative for a Swing-held instrument.

If Swing publishes strategy income evidence, use the same normalized field names where applicable:

- `income`
- `projected_annual_income`
- `income_events[]`
- `holdings[].annual_income`
- `holdings[].yearly_distribution_yield_percent`
- `holdings[].payment_frequency`
- `holdings[].next_ex_dividend_date`
- `holdings[].income_analytics_source`

If no authoritative income evidence exists, publish `null` / omit the optional values. The Enterprise UI will display `Not reported` rather than fabricate values.

## Permanent Rules

- Strategy evidence is strategy-scoped.
- Dividend evidence must never populate SWING-001 rows.
- Swing evidence must never populate DIVIDEND-001 rows.
- Realized income and projected income are separate concepts.
- Missing evidence remains `Not reported`.
- The Enterprise host remains read-only, reporting-only, and does not place orders or move capital.
