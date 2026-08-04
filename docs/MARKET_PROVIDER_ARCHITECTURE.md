# Market Provider Architecture

## Purpose

This document records the verified and planned provider architecture for Enterprise Market Data. It supersedes the earlier assumption that Robinhood MCP could not be reached from the DigitalOcean runtime.

## Verified DigitalOcean Capability

The DigitalOcean server has independently completed a Robinhood MCP historical-data request through authenticated Codex.

Verified scope:

- Tool capability: `get_equity_historicals`
- Symbol tested: `SPY`
- Interval tested: daily
- Bars returned: 19
- Date range represented in the verification: July 1 through July 28, 2026
- Data fields returned: open, high, low, close, volume, and session
- Access mode: read-only

A final HTTP 400 response from the DELETE cleanup step is classified as a session-cleanup issue after the successful data response. It does not convert a verified successful retrieval into a provider failure, but it must be logged and addressed independently.

## Permanent Robinhood Restrictions

Only historical market-data access is approved.

The provider must not expose or request:

- Orders
- Order placement
- Order cancellation
- Account information
- Balances
- Positions
- Buying power
- Transfers
- Real capital movement
- Any trading tool

## Initial Provider Priority

For supported historical equity requests:

```text
YFINANCE
-> ROBINHOOD_READ_ONLY
-> VALID_PRIOR_CSV
```

The priority is configuration-owned by Enterprise Core. Strategies do not choose providers.

## Provider Roles

### Yahoo Finance

Role: primary market-data provider.

Expected uses:

- Quotes
- Historical OHLCV
- Dividend evidence
- Split evidence
- Earnings evidence when supported by the existing implementation

Exact production capabilities must be confirmed during direct module inventory and tests. Architecture documents must not treat an untested endpoint as verified.

### Robinhood Read-Only

Role: secondary historical OHLCV provider.

Current verified capability:

- Daily equity historical OHLCV through `get_equity_historicals`

Current unverified or unsupported capabilities:

- Quotes
- Intraday history
- Weekly or monthly history
- Dividend events
- Splits
- Earnings

Unverified capabilities must return `UNAVAILABLE` and must not trigger account or trading tools.

### Valid Prior CSV

Role: final historical fallback.

Requirements:

- File was created from previously normalized and validated market data.
- Symbol and interval match the request.
- Timestamps are ordered and unique.
- Required OHLCV fields are valid.
- Age is declared.
- Response quality is `STALE` unless the freshness policy explicitly proves otherwise.

## Provider Interface

Every adapter implements a common contract:

```text
provider_id
capabilities
health
get_quote
get_history
get_dividends
get_splits
get_earnings
```

A provider may implement only declared capabilities. Unsupported calls return a structured unavailable response.

## Enterprise Historical Pipeline

```text
Strategy historical request
    -> Enterprise Market Data API
    -> request validation
    -> Provider Priority Engine
    -> Yahoo attempt
    -> Robinhood read-only attempt on eligible failure
    -> valid prior CSV attempt on eligible failure
    -> normalization
    -> OHLCV validation
    -> quality assessment
    -> cache update when allowed
    -> canonical response
```

## Canonical Market Bar

Required fields:

```json
{
  "symbol": "SPY",
  "timestamp": "ISO-8601 UTC",
  "open": 0.0,
  "high": 0.0,
  "low": 0.0,
  "close": 0.0,
  "volume": 0,
  "session": "regular | extended | unknown",
  "interval": "day",
  "provider": "yahoo | robinhood_read_only | csv_archive",
  "adjusted": false,
  "quality": "VERIFIED | PARTIAL | STALE | UNAVAILABLE"
}
```

## Validation Rules

- Symbol is normalized and matches the request.
- Bars are sorted ascending by timestamp.
- Duplicate timestamps are rejected or deterministically reconciled with a warning.
- Values are finite.
- Prices are positive.
- `high` is not below open, close, or low.
- `low` is not above open, close, or high.
- Volume is non-negative when present.
- Session and interval are explicit.
- Empty results are not successful results.
- Provider and fallback trace are retained.

## Failure Classification

Provider failures should be classified as:

- `AUTHENTICATION_ERROR`
- `CAPABILITY_UNAVAILABLE`
- `TIMEOUT`
- `RATE_LIMITED`
- `EMPTY_RESPONSE`
- `INVALID_RESPONSE`
- `TRANSPORT_ERROR`
- `SESSION_CLEANUP_ERROR`
- `UNKNOWN_ERROR`

A cleanup error after a successful response is recorded separately. It may degrade provider health if repeated, but it does not discard already validated bars.

## Provider Health Metrics

Track per provider:

- Enabled capabilities
- Calls
- Successful calls
- Failed calls
- Empty responses
- Invalid responses
- Cleanup errors
- Average latency
- Consecutive failures
- Last success
- Last failure
- Last validated symbol and interval

## Strategy Integration Boundary

Dividend and Swing strategies receive canonical responses only. They must not:

- Invoke Codex or MCP directly.
- Parse Robinhood tool payloads.
- Select provider priority.
- Treat a provider failure as a trading signal.
- Use stale data without reading the quality metadata.

Strategy-specific sufficiency rules remain strategy-owned. For example, Swing may require a minimum bar count before calculating indicators; that is not a provider-selection decision.

## Stage 2 Implementation Order

1. Freeze canonical request and response models.
2. Add provider interface and capability declarations.
3. Adapt existing Yahoo implementation.
4. Implement the DigitalOcean Robinhood read-only bridge.
5. Implement valid-prior-CSV adapter.
6. Implement provider priority policy.
7. Implement normalization and validation.
8. Add provider health and fallback trace.
9. Integrate Swing through a client adapter with its current local path retained for rollback.
10. Integrate Dividend after Swing historical validation and dividend-event evidence inventory.

## Stage 1 Decision

Robinhood read-only historicals are no longer hypothetical. They are a verified secondary provider capability and must be included in the Stage 1 architecture freeze, while all trading and account capabilities remain permanently excluded.
