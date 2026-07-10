# Version 1.1 Read-Only Market Data Policy

## Purpose

Version 1.1 permits outbound access to approved public market-data providers so the Dividend Bot can replace placeholder values with current and historical market information.

## Approved Access

- Yahoo Finance through `yfinance`
- Read-only quote retrieval
- Read-only historical price retrieval
- Read-only dividend and distribution history retrieval
- Read-only basic fundamentals retrieval
- Local JSON caching
- Fresh-cache reuse
- Stale-cache fallback during provider outages

## Permanent Restrictions

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- No brokerage authentication
- No account access
- No order creation
- No order submission
- No trade execution
- No portfolio mutation through external services

## Architecture

All market-data access must pass through:

1. `market_data_provider.py`
2. `yahoo_finance_provider.py`
3. `market_data_cache.py`

Analysis engines must not independently access external market-data services.

## Cache Policy

Default freshness windows:

- Quotes: 5 minutes
- Price history: 6 hours
- Dividend history: 24 hours

When the live provider is unavailable, the service may return stale cached data with:

- `data_source=CACHE_STALE_FALLBACK`
- `is_stale=True`
- `provider_warning`

## Dependency

`yfinance` is an approved Version 1.1 dependency and is already listed in `requirements.txt`.

## Status

Architecture policy: APPROVED

Version: 1.1
