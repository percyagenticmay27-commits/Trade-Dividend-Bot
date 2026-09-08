# Stooq Symbol Normalization Version 1

## Purpose

This update makes the Enterprise Market Data Provider own Stooq-specific symbol formatting and ensures quote and history requests use the same canonical download URL.

## Rules

Examples:

```text
SOXL -> soxl.us
TQQQ -> tqqq.us
SPY  -> spy.us
AAPL -> aapl.us
BRK.B -> brk.b
```

YFinance, Robinhood MCP, and local-cache identifiers remain canonical uppercase symbols.

## Production entry point

The systemd service now invokes:

```text
/home/tradebot/Trade-Dividend-Bot/refresh_enterprise_market_data_normalized.py
```

This entry point preserves the existing refresh orchestration and replaces only the Stooq transport with the provider-aware implementation.

## Stooq endpoint

Both quote and history use:

```text
https://stooq.com/q/d/l/?s=<provider_symbol>&i=d
```

The source sends an explicit user agent and CSV Accept header and rejects HTML responses.

## Diagnostics

The provider distinguishes:

```text
STOOQ_DOWNLOAD_ENDPOINT_HTTP_404
STOOQ_RATE_LIMITED
STOOQ_UPSTREAM_UNAVAILABLE
STOOQ_NON_CSV_RESPONSE
STOOQ_SYMBOL_OR_DOWNLOAD_UNAVAILABLE
```

A valid Stooq quote webpage proves the symbol exists, but it does not necessarily prove that the CSV download endpoint is currently available. A remaining `STOOQ_DOWNLOAD_ENDPOINT_HTTP_404` after this update therefore identifies a Stooq download-endpoint/access issue rather than symbol-suffix drift.

## Safety

This change does not alter provider precedence, valuation calculations, stale-data protection, paper-only rules, allocation state, broker execution, or Robinhood behavior.
