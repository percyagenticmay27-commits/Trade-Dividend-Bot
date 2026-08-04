# Plugin Specification Version 1

## Purpose

This specification defines how independent paper-only strategies publish identity, status, health, outputs, state summaries, and reports to the Enterprise Trade Platform.

A plugin remains an independent codebase and independently runnable process. AI CIO discovers and monitors plugins through contracts; it does not import strategy calculation code.

## Permanent Safety Requirements

Every plugin must declare and enforce:

```json
{
  "paper_trade_mode": true,
  "live_trading_enabled": false,
  "broker_execution_enabled": false,
  "order_placement_enabled": false
}
```

Registration must fail when any required safety field is missing, false, contradictory, or not boolean.

## Required Plugin Artifacts

```text
manifest.json
status.json
health.json
outputs.json
```

Recommended directories:

```text
reports/
results/
logs/
state/
```

The directory names may differ during migration when the manifest explicitly declares their locations.

## Manifest Contract

Required fields:

```json
{
  "schema_version": "1.0",
  "strategy_id": "DIVIDEND-001",
  "strategy_name": "Dividend Strategy",
  "strategy_type": "DIVIDEND_ETF",
  "strategy_class": "INCOME",
  "version": "1.0.0",
  "lifecycle_status": "PRODUCTION",
  "runtime_status": "ONLINE",
  "paper_trade_mode": true,
  "live_trading_enabled": false,
  "broker_execution_enabled": false,
  "order_placement_enabled": false,
  "supported_contract_versions": ["1.0"],
  "capabilities": [],
  "artifact_locations": {},
  "generated_at": "ISO-8601 UTC"
}
```

Rules:

- `strategy_id` is stable and unique.
- `version` follows semantic versioning.
- Artifact paths are relative to the plugin root unless explicitly declared as deployment paths.
- Capabilities describe strategy outputs, not enterprise infrastructure.
- A strategy must not claim provider, broker, account, order, or real-capital capabilities.

## Status Contract

Required fields:

```json
{
  "schema_version": "1.0",
  "strategy_id": "DIVIDEND-001",
  "runtime_status": "ONLINE | OFFLINE | DEGRADED | ERROR | UNKNOWN",
  "last_run_started_at": null,
  "last_run_completed_at": null,
  "last_success_at": null,
  "last_failure_at": null,
  "run_count": 0,
  "success_count": 0,
  "failure_count": 0,
  "current_run_id": null,
  "generated_at": "ISO-8601 UTC"
}
```

Rules:

- Counts are non-negative integers.
- `failure_count <= run_count`.
- `success_count <= run_count`.
- Timestamps are ISO-8601 UTC.
- Status reports runtime facts only and must not contain investment scoring logic.

## Health Contract

Required fields:

```json
{
  "schema_version": "1.0",
  "strategy_id": "DIVIDEND-001",
  "health_status": "OK | WARNING | ERROR | UNKNOWN",
  "score": 100,
  "required_files_present": true,
  "missing_required_files": [],
  "warnings": [],
  "errors": [],
  "checks": [],
  "generated_at": "ISO-8601 UTC"
}
```

Rules:

- `score` is between 0 and 100.
- `required_files_present=true` cannot coexist with non-empty `missing_required_files`.
- Strategy-specific health calculations remain inside the strategy.
- AI CIO validates and aggregates the artifact but does not recreate its calculations.

## Outputs Contract

Required fields:

```json
{
  "schema_version": "1.0",
  "strategy_id": "DIVIDEND-001",
  "report_files": [],
  "data_files": [],
  "state_summary_files": [],
  "log_files": [],
  "latest_report": null,
  "latest_data_file": null,
  "output_count": 0,
  "missing_outputs": [],
  "warnings": [],
  "generated_at": "ISO-8601 UTC"
}
```

Rules:

- Paths must be declared and readable by the plugin runtime.
- State exposure should use summaries or read-only artifacts; private operational state need not be published wholesale.
- AI CIO must not modify strategy-owned state files through this contract.

## Required Strategy Behavior

Every plugin must:

1. Remain independently runnable.
2. Publish all four required artifacts.
3. Preserve deterministic paper-only safety fields.
4. Use enterprise market data after migration, with an explicitly documented temporary rollback path.
5. Publish strategy-owned calculations rather than asking AI CIO to reproduce them.
6. Record warnings for missing optional evidence and errors for missing required evidence.
7. Preserve append-only ledgers where the strategy owns such ledgers.
8. Include unit tests for contract generation and validation.

## Prohibited Plugin Behavior

A plugin must not:

- Place, submit, cancel, replace, or simulate submission of a real broker order.
- Access Robinhood account, balance, position, or trading tools.
- Own enterprise provider selection.
- Own shared market-data cache policy after migration.
- Own cross-strategy paper cash or allocation governance.
- Import another strategy's calculation modules.
- Modify another plugin's state.
- represent stale data as current or verified.

## Dividend Plugin Ownership

The Dividend plugin continues to own:

- Dividend screening and ranking.
- Dividend safety, consistency, growth, coverage, yield, cut, and suspension analysis.
- Dividend lifecycle, simulated holdings, forecasts, calendars, alerts, reviews, learning, replacement analysis, and strategy health.
- Dividend reports and recommendations.

It does not permanently own enterprise provider priority, shared cache, cross-strategy cash, allocation governance, or enterprise dashboards.

## Swing Plugin Ownership

The Swing plugin continues to own:

- Opportunity Quality.
- Momentum, market regime, confidence, technical analysis, and entry timing.
- Strategy A and Strategy B lifecycle decisions.
- Swing paper positions, trailing stops, exits, reentry cooldowns, and trade ledger.
- Swing reports and recommendations.

It consumes the enterprise historical provider chain:

```text
YFINANCE
-> ROBINHOOD_READ_ONLY
-> VALID_PRIOR_CSV
```

The chain is implemented by Enterprise Core, not by Swing strategy calculations.

## Registration Lifecycle

```text
DISCOVERED
-> VALIDATING
-> REGISTERED
-> ONLINE or DEGRADED
-> OFFLINE
```

Registration fails when:

- Required artifacts are missing.
- Schema validation fails.
- Safety fields fail closed.
- Strategy ID conflicts with an existing plugin.
- Contract versions are incompatible.

## Compatibility and Versioning

- Version 1 artifacts use `schema_version=1.0`.
- Additive optional fields are compatible.
- Required-field removals or semantic changes require a major schema version.
- AI CIO must continue reading a supported older schema during a documented migration window.

## Migration Rule

Existing Dividend and Swing repositories are not moved wholesale into an enterprise repository during Stage 1. They first publish compliant artifacts and consume shared services through adapters. Repository consolidation, if ever approved, is a separate decision.
