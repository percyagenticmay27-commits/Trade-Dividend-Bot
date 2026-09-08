# Enterprise Market Data Historical Bar Export Version 1.0

## Purpose

The Dividend AI CIO Enterprise Market Data Provider now publishes the actual normalized historical bars required by `SWING-001`. This closes the provider-output gap where strategy status contained only `latest_bar_date` and `bar_count` metadata.

No Swing calculations, allocation rules, or stale-data protections are changed.

## Authoritative output directory

DigitalOcean path:

```text
/home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_history
```

Per-symbol files:

```text
SOXL.history.json
SOXL.csv
TQQQ.history.json
TQQQ.csv
```

## JSON export contract

Pattern:

```text
{symbol}.history.json
```

Fields:

```text
schema_version
strategy_id
symbol
period
interval
provider
generated_at
latest_bar_date
stale
corporate_action_adjusted
split_history
dividend_history
cache_used
warnings
bars
```

Each bar contains:

```text
date
open
high
low
close
adjusted_close
volume
```

## CSV export contract

Pattern:

```text
{symbol}.csv
```

Header order:

```csv
date,open,high,low,close,adjusted_close,volume
```

The CSV is provider-neutral and intended for the Swing Phase 2 sync step. Swing may copy or transform it into its local `data/SOXL.csv` and `data/TQQQ.csv` paths, but it must preserve its existing freshness validation and must never treat a stale export as valid.

## Atomicity

Both JSON and CSV exports are written using the AI CIO atomic-write helper. A consumer must never observe a partially written file.

## Strategy status linkage

Each symbol's `history` object in:

```text
results/enterprise_market_data_status.json
```

now includes:

```text
bars_json_path
bars_csv_path
```

The machine-readable provider contract in:

```text
results/enterprise_market_data_contract.json
```

now includes `history_exports` with the export directory, file patterns, CSV fields, and atomic-write guarantee.

## SWING-001 rules

- Required symbols are `SOXL` and `TQQQ`.
- Both quote and history must be fresh.
- `BLOCKED` must stop market-data-dependent Swing publication.
- Entry price must never substitute for missing current price.
- Stale local CSV files must never become an implicit fallback.
- The existing `$4,500` allocation remains unchanged.
- Swing must remain provider-neutral and must not call Codex, Robinhood, YFinance, or Stooq directly.

## Validation command

After deployment:

```bash
sudo systemctl restart enterprise-market-data-refresh.service
ls -l /home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_history
head -5 /home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_history/SOXL.csv
head -5 /home/tradebot/Trade-Dividend-Bot/results/enterprise_market_data_history/TQQQ.csv
```
