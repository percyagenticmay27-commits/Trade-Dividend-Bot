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
