# Discovery Leadership — AI CIO Market Snapshot Integration

## Production data authority

Discovery Leadership consumes the existing AI CIO read-only market-data contract in `market_data_snapshot.json`.

Production flow:

`MarketDataService -> MarketDataCache -> market_data_snapshot.json -> Discovery Leadership -> enterprise_swing_discovery_bucket.json -> SWING-001`

The weekly Discovery Leadership producer does not read `/home/tradebot/Trade-Swing-Bot/main/data` and does not create a second authoritative historical market-data store.

## Weekly coverage preflight

Before leadership enrichment, the weekly generator verifies that the AI CIO snapshot contains `SPY` plus every currently nomination-eligible discovery candidate.

If all required symbols are present, no market-data refresh is performed.

If coverage is incomplete, the generator invokes the existing cache-backed `write_market_data_snapshot()` path with the required symbols and `force_refresh=False`. Fresh cached data therefore remains preferred, and the established provider/stale-cache fallback policy remains authoritative.

If a required symbol still cannot be obtained, it stays missing and leadership evidence fails closed. No return, relative multiple, leadership score, or ranking input is fabricated.

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
- Missing provider coverage remains explicit after the preflight rather than being inferred.
- Existing SWING-001 top-level contract remains `schema_version=1.0`, `strategy_id=SWING-001`, and `candidates=[]`.

## Compatibility

The CSV-based loader in `discovery_leadership.py` remains as a deterministic compatibility/unit-test path. It is not the production weekly-data authority.
