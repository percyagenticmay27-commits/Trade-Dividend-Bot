# Enterprise Market Data Provider Version 1.0

AI CIO-owned, strategy-neutral, read-only market-data service.

## Provider precedence
1. Robinhood MCP through `/usr/bin/codex exec`
2. yfinance
3. Stooq
4. prior valid normalized local cache
5. safe failure

Freshness is mandatory. Stale cache or provider data is rejected. A required-symbol failure blocks only the requesting strategy; an optional-symbol failure is a warning.

## Contract
`get_quote`, `get_history`, `get_latest_close`, `get_previous_close`, `get_volume`, `get_split_history`, and `get_dividend_history`.

The provider owns selection, normalization, freshness, cache validation, health, and evidence. Strategy repositories do not know which upstream provider succeeded.

## Robinhood bridge
`codex_robinhood_market_data_bridge.py` invokes the server's authenticated `robinhood-trading` MCP connection through noninteractive `codex exec`. It allowlists quote/history operations, rejects order-related operations, has a strict timeout, fails closed, strips the child environment, writes no OAuth material, and accepts only one JSON object.

## Evidence
- `results/enterprise_market_data_status.json`
- `results/enterprise_market_data_provider_health.json`
- `results/enterprise_market_data_refresh.csv`
- `results/enterprise_market_data_contract.json`

## Deployment
Install `yfinance` in the Dividend AI CIO virtual environment if approved. The service still falls through to Stooq/cache when unavailable.

```bash
/home/tradebot/Trade-Dividend-Bot/.venv/bin/python refresh_enterprise_market_data.py \
  --strategy-id SWING-001 --required-symbol SOXL --required-symbol TQQQ
```

## Swing Phase 2 integration
1. Read `results/enterprise_market_data_contract.json` and treat Version 1.0 as the stable host contract.
2. Replace direct local-CSV primary reads with calls or JSON handoffs from this provider.
3. Use normalized quote/history fields for portfolio valuation, indicators, performance, executive summary, KPI evidence, and email.
4. Preserve Swing stale-data rejection. Never silently fall back to stale Swing CSV files.
5. Required-symbol failures block only `SWING-001`; optional-symbol failures remain warnings.
6. Preserve the existing $4,500 allocation and all Swing calculations.
