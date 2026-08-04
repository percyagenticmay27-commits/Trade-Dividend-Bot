# Enterprise Market Data Provider Version 1.0

AI CIO-owned, strategy-neutral, read-only market-data service.

## Provider precedence
1. Robinhood MCP through root's authenticated `/usr/local/bin/codex exec` profile
2. yfinance
3. Stooq
4. prior valid normalized local cache
5. safe failure

Freshness is mandatory. Stale cache or provider data is rejected. A required-symbol failure blocks only the requesting strategy; an optional-symbol failure is a warning.

## Contract
`get_quote`, `get_history`, `get_latest_close`, `get_previous_close`, `get_volume`, `get_split_history`, and `get_dividend_history`.

The provider owns selection, normalization, freshness, cache validation, health, and evidence. Strategy repositories do not know which upstream provider succeeded.

## Root-owned Robinhood MCP bridge

The server's existing Robinhood OAuth connection belongs to root's Codex profile. Authentication files are never copied to the repository or to the `tradebot` account.

The systemd service remains `User=tradebot`. Only its tightly scoped `ExecStartPre=+` commands run `root_codex_market_data_handoff.py` as root. Those commands:

- allow only `get_quote` and `get_history`;
- invoke `/usr/local/bin/codex exec` with root's existing authenticated profile;
- reject order, buy, sell, cancel, transfer, position, and execution operations;
- use strict timeouts and fail closed;
- reject OAuth, token, cookie, secret, authorization, and account-number fields;
- atomically write mode `0640` normalized JSON into `/run/enterprise-market-data-handoff`;
- change only the handoff file ownership to `tradebot:tradebot`;
- never expose `/root/.codex` to the unprivileged runtime.

The main `refresh_enterprise_market_data.py` process runs as `tradebot`, reads only the normalized handoff, and applies normal provider failover when the handoff is unavailable or invalid.

## Evidence
- `results/enterprise_market_data_status.json`
- `results/enterprise_market_data_provider_health.json`
- `results/enterprise_market_data_refresh.csv`
- `results/enterprise_market_data_contract.json`

## Deployment

Install the service after pulling the branch:

```bash
sudo cp deploy/systemd/enterprise-market-data-refresh.service \
  /etc/systemd/system/enterprise-market-data-refresh.service
sudo systemctl daemon-reload
sudo systemctl start enterprise-market-data-refresh.service
sudo systemctl status enterprise-market-data-refresh.service
```

Review logs:

```bash
sudo journalctl -u enterprise-market-data-refresh.service --no-pager -n 100
```

Install `yfinance` in the Dividend AI CIO virtual environment only if approved. The service still falls through to Stooq and the freshness-validated cache when unavailable.

Manual fallback-only execution as `tradebot` is supported, but Robinhood MCP handoff files must already exist:

```bash
sudo -u tradebot /home/tradebot/Trade-Dividend-Bot/.venv/bin/python \
  /home/tradebot/Trade-Dividend-Bot/refresh_enterprise_market_data.py \
  --strategy-id SWING-001 --required-symbol SOXL --required-symbol TQQQ
```

## Swing Phase 2 integration
1. Read `results/enterprise_market_data_contract.json` and treat Version 1.0 as the stable host contract.
2. Replace direct local-CSV primary reads with calls or JSON handoffs from this provider.
3. Use normalized quote/history fields for portfolio valuation, indicators, performance, executive summary, KPI evidence, and email.
4. Preserve Swing stale-data rejection. Never silently fall back to stale Swing CSV files.
5. Required-symbol failures block only `SWING-001`; optional-symbol failures remain warnings.
6. Preserve the existing $4,500 allocation and all Swing calculations.
