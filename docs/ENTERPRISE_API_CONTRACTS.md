# Enterprise API Contracts

## Purpose

This document freezes the Version 1 contract boundaries between Enterprise Core, AI CIO, and independent strategy plugins before production-code extraction begins.

The contracts define behavior and ownership. They do not require a specific transport. Stage 2 may implement in-process Python interfaces, local HTTP, file artifacts, or a combination, provided the behavior remains compatible.

## Permanent Safety Contract

Every request and response must preserve:

```json
{
  "paper_trade_mode": true,
  "live_trading_enabled": false,
  "broker_execution_enabled": false,
  "order_placement_enabled": false
}
```

A component that cannot prove these values must fail closed.

## Common Response Envelope

Enterprise APIs should return a consistent envelope:

```json
{
  "schema_version": "1.0",
  "request_id": "string",
  "generated_at": "ISO-8601 UTC",
  "status": "OK | WARNING | ERROR | UNAVAILABLE",
  "quality": "VERIFIED | PARTIAL | STALE | UNAVAILABLE",
  "provider": "yahoo | robinhood_read_only | csv_archive | enterprise",
  "warnings": [],
  "errors": [],
  "data": {}
}
```

## Market Data API

### `get_quote`

Inputs:

- `symbol`
- optional maximum age
- optional provider policy

Output data:

- symbol
- timestamp
- price
- open
- high
- low
- previous close when available
- volume when available
- provider
- freshness metadata

### `get_history`

Inputs:

- `symbol`
- `interval`
- `start`
- `end`
- optional adjusted-price policy
- optional session policy

Canonical bar:

```json
{
  "symbol": "SPY",
  "timestamp": "2026-07-28T00:00:00Z",
  "open": 739.19,
  "high": 742.7901,
  "low": 735.98,
  "close": 740.86,
  "volume": 47322247,
  "session": "regular",
  "adjusted": false,
  "provider": "robinhood_read_only"
}
```

Required validation:

- Symbol is normalized.
- Timestamps are ordered and unique.
- `high >= open`, `high >= close`, and `high >= low`.
- `low <= open`, `low <= close`, and `low <= high`.
- Prices are finite and positive.
- Volume is a non-negative integer when present.
- Returned date range and interval are declared.

### `get_dividends`

Inputs:

- `symbol`
- `start`
- `end`

Output data:

- declaration date when available
- ex-dividend date
- record date when available
- payment date when available
- amount
- currency
- provider
- evidence quality

Robinhood historical OHLCV must not be treated as dividend-event evidence.

### `get_splits`

Inputs:

- `symbol`
- `start`
- `end`

Output data:

- effective date
- numerator
- denominator
- provider
- evidence quality

### `get_earnings`

Inputs:

- `symbol`
- optional date range

Output data:

- announced or estimated date
- timing when available
- confirmed flag
- provider
- evidence quality

### `health`

Output data:

- service status
- last successful request
- last failed request
- cache status
- provider summary
- consecutive failures

### `provider_status`

Output data per provider:

- provider ID
- enabled capabilities
- availability
- last success
- last failure
- success count
- failure count
- average latency
- current circuit state

## Provider Contract

Every provider adapter must implement the capabilities it declares and return `UNAVAILABLE` for unsupported capabilities. It must never silently synthesize unsupported data.

Required operations:

- `provider_id()`
- `capabilities()`
- `health()`
- `get_quote()` when declared
- `get_history()` when declared
- `get_dividends()` when declared
- `get_splits()` when declared
- `get_earnings()` when declared

### Current capability declarations

- Yahoo Finance: primary market-data provider; exact validated capabilities remain subject to implementation inventory.
- Robinhood Read-Only: `get_equity_historicals` only, currently verified for daily equity OHLCV through DigitalOcean Codex/MCP.
- CSV Archive: valid prior normalized data only; response quality must be `STALE` unless freshness policy proves otherwise.

## Portfolio API

### `get_cash`

Returns enterprise paper cash, reserved paper cash, available paper cash, update timestamp, and ledger position.

### `get_allocations`

Returns current paper allocations by strategy and any active limits.

### `get_strategy_summary`

Returns only strategy-published portfolio summaries. Enterprise Core must not reconstruct Dividend or Swing lifecycle logic.

### `submit_allocation_request`

Inputs:

- strategy ID
- requested amount
- reason
- evidence references
- idempotency key

Output:

- request ID
- state: `PENDING | APPROVED | REJECTED | CANCELLED`
- governance warnings

This operation may alter paper allocation records only. It may not move real capital or place orders.

## Governance API

### `register_strategy`

Validates and registers a plugin manifest.

### `strategy_health`

Returns the latest plugin-published health artifact and validation status.

### `pending_requests`

Returns pending paper-allocation or governance requests.

### `approve_request` and `reject_request`

Record a governed paper-only decision with actor, timestamp, reason, and immutable audit entry.

## Plugin API

### `discover_plugins`

Returns registered strategy IDs and contract locations.

### `plugin_manifest`

Returns a validated manifest.

### `plugin_status`

Returns current runtime status and last-run metadata.

### `plugin_health`

Returns strategy-published health and validation results.

### `plugin_outputs`

Returns declared output files, latest report references, output counts, and missing-output warnings.

The plugin manager reads artifacts or invokes a declared adapter. It must not import strategy calculation modules into AI CIO.

## Reporting API

### `publish_strategy_report`

Registers a report produced by a strategy without changing its calculations.

### `build_enterprise_summary`

Combines enterprise-owned state and validated strategy-published artifacts.

### `list_reports`

Returns reports by strategy, type, date, and freshness.

## Scheduler API

### `register_job`

Registers an independently runnable service or strategy command.

### `run_job`

Runs a configured paper-only job with a correlation ID and records status.

### `job_status`

Returns last run, duration, exit status, warnings, and artifact freshness.

The scheduler must not absorb strategy logic. Existing strategy launchers remain valid rollback paths during migration.

## Error and Fallback Rules

1. Provider failure is not strategy failure until the provider chain and permitted cache fallback are exhausted.
2. The fallback chain for supported historical requests is configurable and initially:

```text
YFINANCE
-> ROBINHOOD_READ_ONLY
-> VALID_PRIOR_CSV
```

3. A stale cache response must identify its age and carry `quality=STALE`.
4. Missing required data produces `ERROR` or `UNAVAILABLE`; it must not be replaced with invented values.
5. Unsupported Robinhood capabilities must not fall through to account or trading tools.
6. MCP session-cleanup errors occurring after a verified successful data response are logged separately from request success.

## Versioning

- Contract version begins at `1.0`.
- Additive optional fields may be introduced in compatible minor versions.
- Removing, renaming, or changing the meaning of required fields requires a new major version.
- Strategies and AI CIO must report the contract versions they support.
