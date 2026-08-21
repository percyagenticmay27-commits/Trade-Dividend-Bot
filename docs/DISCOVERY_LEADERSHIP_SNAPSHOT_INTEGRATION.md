# Discovery Leadership — AI CIO Market Snapshot Integration

## Production data authority

Discovery Leadership consumes the existing AI CIO read-only market-data contract in `market_data_snapshot.json`.

Production flow:

`MarketDataService -> MarketDataCache -> market_data_snapshot.json -> Discovery Leadership -> enterprise_swing_discovery_bucket.json -> SWING-001`

The weekly Discovery Leadership producer does not read `/home/tradebot/Trade-Swing-Bot/main/data` and does not create a second authoritative historical market-data store.

## Existing evidence preserved

`enterprise_discovery_market_evidence.py` remains the short-horizon evidence layer for weekly return, benchmark-relative strength, volume expansion, and dollar volume.

Discovery Leadership remains a separate longer-horizon layer for 1M, 3M, 6M, YTD, leadership persistence, Trapper 2x-SPY supporting evidence, and peer-based sector/industry leadership.

## Snapshot fields consumed

Per-symbol records use existing fields when available:

- `symbol`
- `sector`
- `industry`
- `history.rows`
- `history_source`
- `is_stale`

SPY is obtained from the same snapshot and is the default benchmark.

## Coverage preflight

Before leadership enrichment, the weekly producer ensures the AI CIO snapshot covers:

- `SPY`
- every current nomination-eligible Enterprise discovery candidate

If all required symbols are already present, no market refresh is performed.

If coverage is missing, the producer calls the existing AI CIO `write_market_data_snapshot()` path with the required symbols and `force_refresh=False`. This keeps the flow cache-first: fresh cached provider responses are reused, while only missing/stale provider needs may require external retrieval under the existing `MarketDataService` rules.

The refresh remains read-only and preserves the existing paper-only market-data safety contract.

## Trapper 2x-SPY evidence consistency

Each available horizon now publishes `trapper_2x_spy_evidence` from the centralized evidence rule in `discovery_leadership.py`.

The same boolean supports leadership classification and the `TRAPPER_2X_SPY_EVIDENCE` explanation reason. This prevents explanation/scoring drift.

The evidence requires a meaningful positive benchmark return, a positive stock return, relative multiple >= 2.0, and at least 5 percentage points of outperformance.

## Safety and failure behavior

- No broker or execution calls are added.
- No BUY/SELL instruction is emitted.
- No Entry Score or Opportunity Quality logic is moved into AI CIO Discovery.
- Missing stock or SPY records yield explicit missing evidence and `null` leadership scores.
- Stale market data is disclosed in candidate warnings.
- Missing `market_data_snapshot.json` leaves the existing base SWING-001 bucket intact instead of fabricating leadership evidence.
- Existing SWING-001 top-level contract remains `schema_version=1.0`, `strategy_id=SWING-001`, and `candidates=[]`.

## Compatibility

The CSV-based loader in `discovery_leadership.py` remains as a deterministic compatibility/unit-test path. It is not the production weekly-data authority.
