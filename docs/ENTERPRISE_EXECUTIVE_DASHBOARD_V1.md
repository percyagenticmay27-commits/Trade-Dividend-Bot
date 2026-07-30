# Enterprise Executive Dashboard Version 1

## Purpose

The Enterprise Executive Dashboard is the read-only AI CIO mission-control report for the Enterprise platform. It combines already-published Strategy Inventory and Enterprise Health outputs into one operational view.

It does not calculate trading signals, inspect strategy-private code, schedule work, allocate capital, request market data, communicate with brokers, or execute orders.

## Module

- `src/dividend_bot/enterprise_executive_dashboard.py`
- Root compatibility wrapper: `enterprise_executive_dashboard.py`

## Required Inputs

- `results/strategy_inventory.json`
- `results/enterprise_health.json`

Missing or invalid required inputs are recorded as explicit dashboard errors.

## Optional Inputs

- `results/runtime_snapshot.json`
- `results/event_statistics.json`
- `results/plugin_registry.json`
- `results/runtime_metrics.json`
- `results/scheduler_status.json`

Missing optional inputs create warnings and do not prevent report generation.

## Outputs

- `results/executive_dashboard.json`
- `results/executive_dashboard.md`

## Dashboard Sections

1. Enterprise Summary
2. Strategy Summary
3. Health Summary
4. Runtime Summary
5. Enterprise Alerts
6. Paper Safety
7. Metadata

## Safety Rules

The dashboard permanently publishes:

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`

Any strategy that does not publish the same safe state forces the dashboard Enterprise status to `UNSAFE`.

## Ownership Boundaries

The dashboard owns aggregation and presentation only. It does not own:

- strategy discovery or registration;
- contract generation;
- heartbeat production;
- strategy health calculations;
- event publication;
- scheduling;
- capital allocation;
- market-data access;
- portfolio decisions;
- brokerage communication or execution.

## Public Functions

- `build_executive_dashboard`
- `write_executive_dashboard_json`
- `render_executive_dashboard_markdown`
- `write_executive_dashboard_markdown`
- `build_and_write_executive_dashboard`

## Validation

```bash
python -m py_compile src/dividend_bot/enterprise_executive_dashboard.py
pytest tests/test_enterprise_executive_dashboard.py -v
```

## Version 1 Freeze Candidate

After local compilation and tests pass, Version 1 may be frozen as the initial Enterprise Operations Layer dashboard. Future HTML or API presentation must consume this output rather than duplicate its aggregation rules.
