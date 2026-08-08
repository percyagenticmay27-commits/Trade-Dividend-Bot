# Swing Projected Income KPI Compatibility Addendum

## Purpose

This addendum records the Enterprise UI evidence contract introduced while completing Dividend strategy-level projected income aggregation.

The Dividend host now propagates strategy-level projected income from strategy-owned dashboard evidence into the Enterprise strategy KPI row. This fixes the case where holding-level `annual_income` values were available but `projected_annual_income` remained `null` at the strategy level.

## Enterprise Fields

Strategies that publish income projections may provide:

- `projected_annual_income`
- `gross_distribution_income`
- `income_adjustments`
- `net_income_received`
- `realized_income_event_count`
- `positive_income_event_count`
- `negative_income_event_count`
- `income_accounting_method`
- `income_evidence_source`
- `income_events`

Missing values must remain `null` / Not reported. The Enterprise host must not fabricate projected or realized income.

## Swing Strategy Guidance

`SWING-001` does not need to implement Dividend-specific distribution calculations. If the Swing strategy later publishes authoritative strategy income, carry, interest, or other income evidence, it may populate the normalized Enterprise fields above using Swing-owned evidence and clearly documented accounting semantics.

Do not derive Swing projected income from Dividend yield rules.

Do not treat realized trade P&L or unrealized market P&L as strategy income.

If projected income is not applicable to Swing, publish `null` or omit the optional field and allow the Enterprise UI to render Not reported / Not applicable according to the strategy contract.

## Safety and Governance

This compatibility change is reporting-only. It must not alter allocation, lifecycle, execution, broker connectivity, paper-trade locks, or strategy selection rules.
