# Swing Phase 2 Enterprise Market Data Migration Guide

## Purpose

This guide defines the exact Phase 2 migration for `SWING-001` after completion of the Dividend AI CIO Enterprise Market Data Provider Version 1.0.

The goal is to replace the Swing Bot's stale local CSV files as its primary market-data source without changing Swing strategy calculations, committee logic, allocation logic, portfolio rules, lifecycle behavior, or paper-only protections.

The Swing repository must preserve its existing stale-data rejection. It must not silently fall back to stale `data/SOXL.csv`, `data/TQQQ.csv`, or any other outdated local market-data file.

## Current production deployment

Dividend AI CIO repository:

```text
/home/tradebot/Trade-Dividend-Bot
```

Provider branch during Phase 1 validation:

```text
feature/enterprise-market-data-provider-v1
```

Enterprise Market Data Provider module:

```text
/home/tradebot/Trade-Dividend-Bot/src/dividend_bot/enterprise_market_data_provider.py
```

Refresh command:

```text
/home/tradebot/Trade-Dividend-Bot/refresh_enterprise_market_data.py
```

Persistent freshness-validated cache:

```text
/var/lib/enterprise-market-data-cache
```

Transient sanitized Robinhood MCP handoff directory:

```text
/run/enterprise-market-data-handoff
```

Systemd service:

```text
enterprise-market-data-refresh.service
```

Installed unit path:

```text
/etc/systemd/system/enterprise-market-data-refresh.service
```

Repository unit template:

```text
/home/tradebot/Trade-Dividend-Bot/deploy/systemd/enterprise-market-data-refresh.service
```

## 1. Provider contract file and path

The stable machine-readable contract is published at:

```text
/home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_contract.json
```

The human-readable contract and operating documentation are published at:

```text
/home/tradebot/Trade-Dividend-Bot/docs/ENTERPRISE_MARKET_DATA_PROVIDER_V1.md
```

The provider exposes these operations:

```text
get_quote(symbol)
get_history(symbol, period, interval)
get_latest_close(symbol)
get_previous_close(symbol)
get_volume(symbol)
get_split_history(symbol)
get_dividend_history(symbol)
```

Phase 2 must treat the Version 1.0 contract as host-owned shared infrastructure. The Swing repository must not import Dividend production modules directly and must not duplicate provider selection logic.

## 2. Service and commands used to request quote and history data

### Normal scheduled refresh

The shared service is:

```bash
sudo systemctl start enterprise-market-data-refresh.service
```

Status:

```bash
sudo systemctl status enterprise-market-data-refresh.service --no-pager
```

Logs:

```bash
sudo journalctl -u enterprise-market-data-refresh.service --no-pager -n 200
```

### Direct SWING-001 refresh

Run as `tradebot`:

```bash
/home/tradebot/Trade-Dividend-Bot/.venv/bin/python \
  /home/tradebot/Trade-Dividend-Bot/refresh_enterprise_market_data.py \
  --strategy-id SWING-001 \
  --required-symbol SOXL \
  --required-symbol TQQQ \
  --cache-dir /var/lib/enterprise-market-data-cache
```

The command refreshes both quote and historical data for each required symbol and writes strategy-level evidence into the Dividend repository `results/` directory.

### Cost-aware provider policy

Routine market data uses:

```text
1. YFINANCE
2. STOOQ
3. fresh LOCAL_CACHE
4. ROBINHOOD_MCP through Codex
5. safe failure
```

The systemd unit performs:

```text
Pass 1: public providers and fresh cache only
Pass 2: invoke Robinhood MCP only for unresolved operations
Pass 3: final validation and evidence publication
```

A normal successful public-provider refresh consumes no Codex usage.

## 3. JSON request and response examples

### Recommended Swing-to-host request contract

Phase 2 should use a small strategy-neutral JSON handoff request. The Swing repository may create this adapter contract without importing Dividend modules.

Quote request:

```json
{
  "schema_version": "1.0",
  "operation": "get_quote",
  "strategy_id": "SWING-001",
  "symbol": "SOXL",
  "required": true
}
```

History request:

```json
{
  "schema_version": "1.0",
  "operation": "get_history",
  "strategy_id": "SWING-001",
  "symbol": "SOXL",
  "period": "1mo",
  "interval": "1d",
  "required": true
}
```

### Normalized quote response

```json
{
  "symbol": "SOXL",
  "price": 140.14999389648438,
  "quote_timestamp": "2026-08-04T19:59:04+00:00",
  "trading_date": "2026-08-04",
  "provider": "YFINANCE",
  "source_type": "LIVE_QUOTE",
  "stale": false,
  "confidence": 0.9,
  "warnings": [],
  "cache_used": false
}
```

### Normalized history response

```json
{
  "symbol": "SOXL",
  "interval": "1d",
  "period": "1mo",
  "provider": "YFINANCE",
  "generated_at": "2026-08-04T19:59:04+00:00",
  "latest_bar_date": "2026-08-04",
  "stale": false,
  "corporate_action_adjusted": false,
  "split_history": [],
  "dividend_history": [],
  "cache_used": false,
  "warnings": [],
  "bars": [
    {
      "date": "2026-08-04",
      "open": 137.5,
      "high": 141.2,
      "low": 136.8,
      "close": 140.15,
      "adjusted_close": 140.15,
      "volume": 12345678
    }
  ]
}
```

### Published SWING-001 strategy status

The actual strategy-level evidence contains both required symbols and both operations:

```json
{
  "strategy_id": "SWING-001",
  "status": "READY",
  "records": [
    {
      "symbol": "SOXL",
      "required": true,
      "status": "FRESH",
      "quote": {
        "provider": "YFINANCE",
        "stale": false
      },
      "history": {
        "provider": "YFINANCE",
        "latest_bar_date": "2026-08-04",
        "stale": false,
        "bar_count": 122
      }
    },
    {
      "symbol": "TQQQ",
      "required": true,
      "status": "FRESH",
      "quote": {
        "provider": "YFINANCE",
        "stale": false
      },
      "history": {
        "provider": "YFINANCE",
        "latest_bar_date": "2026-08-04",
        "stale": false,
        "bar_count": 122
      }
    }
  ],
  "warnings": [],
  "errors": []
}
```

## 4. Evidence output paths

The AI CIO owns these evidence outputs:

```text
/home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_status.json
/home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_provider_health.json
/home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_refresh.csv
/home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_contract.json
```

Persistent normalized cache entries are stored under:

```text
/var/lib/enterprise-market-data-cache
```

Typical entries:

```text
SOXL.quote.json
SOXL.history.json
TQQQ.quote.json
TQQQ.history.json
```

Robinhood MCP handoff files exist only when conditional fallback is required:

```text
/run/enterprise-market-data-handoff/SOXL.quote.json
/run/enterprise-market-data-handoff/SOXL.history.json
/run/enterprise-market-data-handoff/TQQQ.quote.json
/run/enterprise-market-data-handoff/TQQQ.history.json
```

The Swing repository should consume normalized host output, not Robinhood handoff files directly.

## 5. Codex and Robinhood bridge command or service name

Systemd service:

```text
enterprise-market-data-refresh.service
```

Conditional fallback evaluator:

```text
/home/tradebot/Trade-Dividend-Bot/refresh_robinhood_fallback_handoffs.py
```

Root-owned read-only handoff entry point:

```text
/home/tradebot/Trade-Dividend-Bot/root_codex_market_data_handoff.py
```

Codex executable:

```text
/usr/local/bin/codex
```

The bridge invokes the existing root-owned authenticated Robinhood MCP profile only for unresolved `get_quote` or `get_history` operations. It rejects order, buy, sell, cancel, transfer, position, execution, authentication, account, token, OAuth, and secret material.

The Swing repository must not invoke Codex, Robinhood MCP, or the root handoff directly. It must remain provider-neutral.

## 6. Freshness rules

Version 1.0 defaults:

```text
Quote maximum age: 900 seconds
Daily history maximum age: 5 calendar days
```

Rules:

- A quote older than 900 seconds is stale and rejected.
- Daily history whose latest bar is more than 5 calendar days old is stale and rejected.
- A stale provider result does not satisfy a required operation.
- A stale cache entry is rejected.
- The provider continues through the precedence chain after stale data.
- Duplicate identical bars may be normalized once.
- Duplicate bars with conflicting values are rejected.
- Historical bars require valid date, OHLC, and volume fields.
- Invalid high/low relationships are rejected.
- Missing required-symbol quote or history data blocks only the requesting strategy.
- Missing optional-symbol data produces a warning.

Swing's existing stale-data checks must remain in place as a second boundary. Phase 2 must never weaken or remove them.

## 7. Failure and status values

### Strategy-level statuses

```text
READY
WARNING
BLOCKED
```

Meaning:

- `READY`: every required symbol has fresh quote and history data.
- `WARNING`: all required data is fresh, but one or more optional symbols failed.
- `BLOCKED`: one or more required quote or history operations failed or remained stale.

### Per-symbol statuses

```text
FRESH
WARNING
BLOCKED
```

### Provider attempt fields

Each attempt may publish:

```text
provider
success
stale
cache_used
error
latest_bar_date
quote_timestamp
```

### Failure behavior required in Swing

- `READY`: continue the Swing cycle.
- `WARNING`: continue using required-symbol data and surface optional warnings.
- `BLOCKED`: stop only `SWING-001` market-data-dependent publication and valuation steps.
- Never substitute entry price for missing current price.
- Never report cost basis as market value because valuation data is missing.
- Never convert missing unrealized P&L into zero.
- Never publish stale KPI, executive-summary, or email values as fresh.
- Do not block the Dividend strategy because `SWING-001` is blocked.

## 8. DigitalOcean deployment path

Dividend AI CIO deployment root:

```text
/home/tradebot/Trade-Dividend-Bot
```

Python environment:

```text
/home/tradebot/Trade-Dividend-Bot/.venv/bin/python
```

Market-data results:

```text
/home/tradebot/Trade-Dividend-Bot/results
```

Systemd unit:

```text
/etc/systemd/system/enterprise-market-data-refresh.service
```

Recommended Phase 2 Swing deployment integration:

- Keep the Swing repository separately deployed.
- Configure the Swing runtime with the absolute host evidence path.
- Use a read-only adapter or copied atomic handoff package generated by the Dividend AI CIO.
- Do not copy OAuth credentials or `/root/.codex`.
- Do not import Dividend source modules into Swing.
- Do not make Swing responsible for provider precedence, caching, health, or normalization.

Recommended environment variables in the Swing service:

```text
ENTERPRISE_MARKET_DATA_STATUS_PATH=/home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_status.json
ENTERPRISE_MARKET_DATA_CONTRACT_PATH=/home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_contract.json
ENTERPRISE_MARKET_DATA_HEALTH_PATH=/home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_provider_health.json
```

If Linux permissions prevent direct read-only access, create an AI CIO-owned atomic export directory readable by the Swing service account. Do not loosen permissions on the entire Dividend repository.

## 9. Tests and final pass summary

Final focused Phase 1 result on DigitalOcean:

```text
33 passed
```

The suite covered:

- YFinance-first cost-aware precedence
- Stooq fallback
- Fresh local-cache fallback
- Robinhood MCP conditional fallback
- Robinhood skipped when public data is fresh
- Only unresolved operations invoke Robinhood
- Stale-cache rejection
- Safe failure with no fresh source
- Required-symbol strategy-scoped blocking
- Optional-symbol warnings
- Quote and history normalization
- Source and timestamp preservation
- Atomic writes
- Conflicting duplicate-bar rejection
- Adjusted-close handling
- Split metadata handling
- Provider health reporting
- Aggregated SOXL and TQQQ evidence
- Quote and history evidence for every symbol
- No authentication data in outputs
- No broker execution or order path
- No capital-allocation leakage
- No repository-local runtime dependency
- Conditional systemd fallback design

Validated production result:

```text
strategy_id: SWING-001
status: READY
```

Both `SOXL` and `TQQQ` returned:

```text
record_status: FRESH
quote_stale: false
history_stale: false
latest_bar_date: 2026-08-04
history bar count: 122
```

The successful provider during validation was `YFINANCE`. Robinhood remained available as a conditional last market-data fallback.

## 10. SWING-001-specific Phase 2 integration instructions

### Permanent rules

- Preserve the existing `$4,500` `SWING-001` allocation.
- Do not modify Dividend production allocation state.
- Do not change Swing strategy calculations.
- Do not change Opportunity Quality calculations.
- Do not change committee ranking, discovery, watchlist, allocation, entry, exit, lifecycle, or paper-only rules.
- Do not import Dividend production modules into Swing.
- Do not duplicate provider selection logic in Swing.
- Do not remove stale-data rejection.

### Step 1: Add a Swing-owned contract adapter

Create a small module in the Swing repository, for example:

```text
src/swing_trade_bot/enterprise_market_data_client.py
```

Its responsibilities must be limited to:

- Read the host contract file.
- Read the AI CIO-published strategy status or atomic export package.
- Validate schema version `1.0`.
- Select the requested symbol record.
- Return normalized quote or historical data.
- Raise a Swing-owned `MarketDataUnavailable` exception on missing, stale, malformed, or blocked data.

It must not:

- Import Dividend modules.
- Know whether YFinance, Stooq, cache, or Robinhood supplied the data.
- Call Robinhood or Codex.
- Perform allocation or portfolio calculations.

### Step 2: Replace primary local-CSV reads

Trace all direct reads of:

```text
data/SOXL.csv
data/TQQQ.csv
```

and any generic `data/{symbol}.csv` primary market-data access.

Replace the primary source for these consumers:

1. Paper Portfolio Manager valuation
2. Current prices
3. Historical bars
4. Technical indicators
5. Performance analytics
6. Executive summary CSV
7. Enterprise KPI evidence
8. Daily email

Local CSV files may remain only as explicitly labeled non-primary fixtures, development samples, or historical archives. They must not silently become the production fallback.

### Step 3: Portfolio valuation behavior

For each open position:

- Use the normalized fresh quote `price` as `current_price`.
- Compute `market_value` using existing Swing calculations.
- Compute unrealized P&L using existing Swing calculations.
- Preserve cost basis and entry price.
- Record provider-neutral source timestamp metadata.
- Block valuation publication for the affected strategy when required data is unavailable.

Never use entry price as a substitute for missing current price.

### Step 4: Historical analytics behavior

Use normalized `bars` for:

- Technical indicators
- Momentum calculations
- Performance analytics
- Trailing calculations
- Historical comparisons

Validate:

```text
stale == false
latest_bar_date is acceptable
bars are non-empty
bars are ordered by date
required OHLCV fields exist
```

### Step 5: Runtime orchestration order

Recommended Swing cycle order:

```text
1. Confirm host contract Version 1.0
2. Confirm SWING-001 status is READY or permitted WARNING
3. Load required SOXL and TQQQ quote/history records
4. Run Paper Portfolio Manager valuation
5. Run technical and performance analytics
6. Generate executive summary
7. Publish Enterprise KPI evidence
8. Generate daily email
```

If status is `BLOCKED`, stop steps 4 through 8 for `SWING-001` and publish a clear blocked-state report instead of stale or fabricated values.

### Step 6: Required Swing tests

Add regression tests covering:

- Contract Version 1.0 accepted
- Unknown contract version rejected
- SOXL and TQQQ records loaded
- Fresh quote accepted
- Stale quote rejected
- Fresh history accepted
- Stale history rejected
- Missing required quote blocks SWING-001
- Missing required history blocks SWING-001
- Optional-symbol failure warns
- Entry price is never substituted for missing current price
- Market value is recomputed from fresh quote
- Unrealized P&L is recomputed from fresh quote
- Historical bars feed existing indicators unchanged
- Executive summary uses fresh values
- Enterprise KPI evidence uses fresh values
- Daily email uses fresh values
- Provider name does not alter calculations
- No Dividend production imports
- No Robinhood or Codex calls from Swing
- Existing `$4,500` allocation unchanged
- Existing stale-data protection preserved

### Step 7: Phase 2 acceptance criteria

Phase 2 is complete only when:

- Swing no longer uses local CSV files as its primary production market-data source.
- SOXL and TQQQ valuation uses current AI CIO-published prices.
- `market_value` no longer defaults to cost basis because data is missing.
- `unrealized_pnl` no longer defaults to zero because data is missing.
- Historical indicators use fresh normalized bars.
- Executive summary, Enterprise KPIs, dashboard ingestion, and daily email use refreshed values.
- Required-symbol failures block only `SWING-001`.
- All existing Swing calculations and the `$4,500` allocation remain unchanged.
- All Phase 2 regression tests pass.

## Explicit non-goals

Phase 2 must not add:

- New strategy logic
- New allocation logic
- New trade-entry or exit rules
- New broker execution
- New live-order behavior
- New AI committees
- New dashboard redesign
- New Dividend strategy calculations

This phase is strictly a market-data source migration and integration task.
