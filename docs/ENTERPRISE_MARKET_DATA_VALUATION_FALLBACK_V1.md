# Enterprise Market Data Valuation Fallback Version 1.0

## Purpose

Prevent `SWING-001` from being blocked solely because a live quote is unavailable when the Enterprise Market Data Provider has already validated fresh historical bars for the same symbol.

## Rule

When all live quote sources fail but normalized history is fresh and contains a latest bar:

1. Use `adjusted_close` from the latest bar when present.
2. Otherwise use `close`.
3. Publish the value as an explicit valuation fallback, not as a live quote.
4. Set `source_type` to `HISTORICAL_CLOSE_FALLBACK`.
5. Set `valuation_fallback` to `true`.
6. Set per-symbol and strategy status to `WARNING` rather than `BLOCKED`.
7. Preserve all failed live-quote attempts in warnings and evidence.

The strategy remains `BLOCKED` when fresh history is also unavailable, stale, empty, malformed, or lacks both `adjusted_close` and `close` on the latest bar.

## Example

```json
{
  "price": 140.25,
  "quote_timestamp": "2026-08-04T22:08:44+00:00",
  "trading_date": "2026-08-04",
  "provider": "YFINANCE",
  "source_type": "HISTORICAL_CLOSE_FALLBACK",
  "stale": false,
  "confidence": 0.75,
  "cache_used": false,
  "valuation_fallback": true,
  "warnings": [
    "live quote unavailable; using latest validated historical close for valuation"
  ]
}
```

## Swing integration

Swing must treat this value as a valid fresh valuation price while preserving the warning in its reports. Swing must not relabel it as an intraday or real-time quote.

No strategy calculations, allocations, stale-history protections, order logic, or paper-only rules are changed.
