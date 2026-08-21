# AI CIO Discovery Leadership v1 — Freeze Candidate

Status: **FREEZE CANDIDATE — pending final server regression validation**

Date: 2026-08-21

## Architectural boundary

AI CIO discovers market leadership. SWING-001 evaluates the trade setup.

Discovery Leadership is advisory discovery evidence only. It does not create BUY/SELL instructions, orders, position sizing, stop loss, take profit, Entry Score, Opportunity Quality, pullback/base/pivot rules, or Swing execution logic.

## Production data authority

Production authority is the existing AI CIO read-only market-data layer:

`MarketDataService -> MarketDataCache -> market_data_snapshot.json -> Discovery Leadership -> results/enterprise_swing_discovery_bucket.json -> SWING-001`

The weekly producer is cache-first and ensures coverage for SPY plus nomination-eligible discovery candidates through the existing `write_market_data_snapshot(..., force_refresh=False)` path when coverage is missing.

It does not read Swing-owned market files and does not create a second authoritative historical-data store.

## Frozen v1 leadership horizons

- 1M: 21 aligned trading sessions
- 3M: 63 aligned trading sessions
- 6M: 126 aligned trading sessions
- YTD: first aligned session of the current year through the latest common session

Benchmark: `SPY`

## Relative leadership classifications

Relative outperformance is measured in percentage points versus SPY.

- WEAK: below -5 percentage points
- MARKET_PERFORMER: -5 through +5
- STRONG: above +5 through +12
- LEADER: above +12 through +25
- EXCEPTIONAL_LEADER: above +25

The Trapper-style approximately 2x-SPY concept is supporting evidence, not a hard gate.

## Trapper 2x-SPY evidence rule

A horizon receives `trapper_2x_spy_evidence=true` only when all conditions hold:

- relative multiple is available and >= 2.0
- stock return is positive
- SPY return is at least +1.0%
- relative outperformance is at least +5 percentage points

This boolean is the single evidence flag used by both classification support and the `TRAPPER_2X_SPY_EVIDENCE` explanation reason.

Negative or near-zero SPY periods do not produce a meaningful relative multiple.

## Leadership persistence

`leadership_persistence = leader_horizons / evaluated_horizons`

A horizon counts as a leader horizon only when its classification is LEADER or EXCEPTIONAL_LEADER.

## Composite score weights

Available components are normalized over their available weights:

- 60% relative stock leadership versus SPY
- 15% sector leadership
- 15% industry leadership
- 5% explicit theme momentum
- 5% source confluence

Missing optional evidence is not fabricated and does not automatically reject a candidate.

If relative stock/benchmark evidence itself is unavailable, the composite leadership score remains null.

## Sector / industry v1 behavior

Sector and industry metadata come first from the AI CIO market snapshot.

Peer leadership uses discovery-candidate peer averages and requires at least two evaluable peers in the group. Insufficient peer evidence remains explicit. V1 does not infer sector or industry leadership from a single nominee.

A future version may replace or augment discovery-peer comparison with authoritative sector/industry benchmark universes without changing the SWING-001 base contract.

## Existing evidence preserved

`enterprise_discovery_market_evidence.py` remains the short-horizon discovery evidence layer for weekly return, SPY-relative strength, volume expansion, and dollar volume.

Discovery Leadership remains the longer-horizon persistence/ranking layer. The two responsibilities are intentionally separate.

## SWING-001 compatibility contract

Top level remains:

```json
{
  "schema_version": "1.0",
  "strategy_id": "SWING-001",
  "candidates": []
}
```

Existing required candidate fields remain preserved. Leadership fields are additive.

## Safety / failure behavior

- Paper-only architecture remains unchanged.
- No broker execution is added.
- Missing SPY or stock history produces explicit missing evidence rather than fabricated values.
- Stale data is disclosed.
- Missing market snapshot preserves the base SWING-001 bucket.
- No hard 20-stock AI CIO limit is introduced.

## First real validation evidence

The first real server run produced five SWING-001 candidates and preserved the discovery/execution boundary:

- AMAT: strongest persistent leader in the observed candidate set
- SJM: multi-horizon leader
- ULTA: recent strength but weak 6M/YTD persistence
- INTS: weak longer-horizon leadership
- FSBW: weak longer-horizon leadership

The real bucket retained `schema_version=1.0`, `strategy_id=SWING-001`, and contained no forbidden trade fields.

## Freeze condition

This v1 freeze becomes authoritative after the final focused regression suite passes on the AI CIO server after the Trapper explanation-consistency hardening.
