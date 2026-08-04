# Twelve Data Provider Version 1

## Purpose

Twelve Data is the second production market-data source for the Enterprise AI CIO. It reduces reliance on YFinance without consuming Codex credits.

## Production precedence

1. YFINANCE
2. TWELVE_DATA, when `TWELVE_DATA_API_KEY` is configured
3. LOCAL_CACHE, only when fresh
4. ROBINHOOD_MCP through Codex
5. Historical-close valuation fallback or safe failure

Stooq remains experimental and is not active in the production refresh chain because its unattended CSV endpoint currently returns a JavaScript browser-verification page.

## Runtime secret

The API key must be stored only on DigitalOcean in:

`/etc/tradebot/enterprise-market-data.env`

Example:

`TWELVE_DATA_API_KEY=replace-with-real-key`

Required permissions:

```bash
sudo install -d -m 0750 -o root -g tradebot /etc/tradebot
sudo touch /etc/tradebot/enterprise-market-data.env
sudo chown root:tradebot /etc/tradebot/enterprise-market-data.env
sudo chmod 0640 /etc/tradebot/enterprise-market-data.env
```

The key must never be committed, printed in evidence, copied into the repository, or included directly in the systemd unit.

## Supported operations

- `get_quote(symbol)` through Twelve Data `/quote`
- `get_history(symbol, period, interval)` through Twelve Data `/time_series`
- latest close, previous close, and volume through the normalized provider contract

Supported Version 1 intervals include `1d`, `1h`, `30m`, `15m`, `5m`, and `1m`.

## Normalization

Quotes publish the existing normalized quote fields. History publishes normalized OHLCV bars. Twelve Data fallback history does not claim adjusted-close or corporate-action support.

## Failure values

- `TWELVE_DATA_RATE_LIMITED`
- `TWELVE_DATA_AUTH_FAILED`
- `TWELVE_DATA_UPSTREAM_UNAVAILABLE`
- `TWELVE_DATA_INVALID_JSON`
- `TWELVE_DATA_INVALID_RESPONSE`
- `TWELVE_DATA_API_ERROR_<code>`
- `TWELVE_DATA_QUOTE_FIELDS_MISSING`
- `TWELVE_DATA_NO_HISTORY_ROWS`
- `TWELVE_DATA_UNSUPPORTED_INTERVAL_<interval>`

All failures continue to the next provider. No failure permits stale or invented data.

## Safety

This integration is read-only and does not alter paper-only protections, allocations, order placement, broker execution, or capital movement.
