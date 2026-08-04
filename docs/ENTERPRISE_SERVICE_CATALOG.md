# Enterprise Service Catalog

## Purpose

This catalog defines the permanent ownership, scope, consumers, dependencies, and migration status of shared enterprise services and independent strategy plugins.

Stage 1 is documentation-only. No production module is moved or removed by this document.

## Permanent Safety Boundary

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- `order_placement_enabled=False`
- Robinhood access is read-only market-data access only.
- No account, balance, position, order, or capital-movement capability is permitted.

## Ownership Rule

Every service has one authoritative owner. Strategies consume enterprise services through frozen contracts and do not duplicate shared infrastructure.

## Core Infrastructure Services

| Service | Owner | Purpose | Primary consumers | Migration status |
|---|---|---|---|---|
| Configuration Service | Enterprise Core | Load validated runtime settings, provider priority, paths, feature flags, and safety controls. | All services and strategies | Planned |
| Scheduler | Enterprise Core | Orchestrate service and strategy runs while preserving independent strategy launchers. | AI CIO, Dividend, Swing | Planned |
| Logging Service | Enterprise Core | Standardize structured operational logs and correlation identifiers. | All services and strategies | Planned |
| Health Monitoring | Enterprise Core | Aggregate service, provider, and strategy health without recalculating strategy results. | AI CIO, dashboards | Planned |
| Secrets Boundary | Enterprise Core | Define secure runtime access to provider credentials without exposing them to strategy code. | Provider adapters only | Planned |
| Notification Service | Enterprise Core | Deliver email and future notification channels from published events. | Reporting, AI CIO, strategies | Future; existing Dividend delivery remains local initially |

## Market Data Services

| Service | Owner | Purpose | Inputs | Outputs | Migration status |
|---|---|---|---|---|---|
| Enterprise Market Data API | Enterprise Core | Provide normalized market data through one strategy-neutral interface. | Symbol, interval, date range, request policy | Canonical quote, bar, dividend, split, earnings, and health responses | Stage 2 target |
| Provider Priority Engine | Enterprise Core | Select providers by configured capability and priority. | Request type, provider policy, provider health | Selected provider result and fallback trace | Stage 2 target |
| Yahoo Finance Provider | Enterprise Core | Primary market-data adapter. | Canonical request | Provider response converted to canonical models | Copy then deprecate local duplicate |
| Robinhood Read-Only Provider | Enterprise Core | Secondary historical OHLCV adapter through the authenticated DigitalOcean Codex/MCP path. | Historical request | Canonical historical bars | Verified for daily equity historicals; Stage 2 target |
| CSV Archive Provider | Enterprise Core | Final fallback using valid prior normalized CSV data. | Historical request and cache policy | Canonical stale or archived bars | Stage 2 target |
| Market Data Normalizer | Enterprise Core | Convert provider-specific payloads into canonical models. | Raw provider payload | Canonical market-data objects | Stage 2 target |
| Market Data Validator | Enterprise Core | Validate symbol, timestamps, OHLC relationships, volume, completeness, and freshness. | Canonical candidate response | Validated response plus quality status | Stage 2 target |
| Shared Market Cache | Enterprise Core | Store validated responses and support controlled stale fallback. | Validated market data | Cached response and cache metadata | Copy then deprecate local duplicate |
| Corporate Action Evidence Service | Enterprise Core candidate | Supply normalized dividend, split, and earnings evidence. | Symbol and date range | Canonical corporate-action records | Ownership frozen as enterprise evidence; implementation pending provider review |

## Portfolio and Governance Services

| Service | Owner | Purpose | Consumers | Migration status |
|---|---|---|---|---|
| Paper Cash Service | Enterprise Core | Own enterprise paper cash and append-only cash history across strategies. | AI CIO, allocation service, strategies through read-only contracts | Planned with state-import and rollback requirements |
| Allocation Service | Enterprise Core | Govern paper allocation requests, approvals, limits, and allocation records. | AI CIO, Dividend, Swing | Existing capability classified for migration |
| Portfolio Summary Service | Enterprise Core | Aggregate strategy-published portfolio summaries without owning strategy-specific lifecycle logic. | AI CIO, dashboards | Planned |
| Governance Service | Enterprise Core | Register strategies, validate permissions, manage approvals, and preserve audit history. | AI CIO, plugin manager, strategies | Planned |
| Audit Service | Enterprise Core | Record immutable governance and allocation decisions. | Governance, AI CIO | Planned |

## Plugin and Contract Services

| Service | Owner | Purpose | Consumers | Migration status |
|---|---|---|---|---|
| Plugin Registry | Enterprise Core | Discover registered strategies and their published manifests. | AI CIO, scheduler, dashboards | Existing registry capability classified for migration |
| Contract Validator | Enterprise Core | Validate manifest, status, health, outputs, readiness, and report schemas. | Plugin registry, AI CIO | Planned |
| Plugin Health Aggregator | Enterprise Core | Aggregate published plugin health; never recalculate strategy health. | AI CIO, dashboards | Planned |
| Release and Readiness Aggregator | Enterprise Core | Combine service and strategy readiness artifacts into enterprise readiness. | AI CIO, operators | Planned |

## Reporting and Intelligence Services

| Service | Owner | Purpose | Consumers | Migration status |
|---|---|---|---|---|
| Enterprise Reporting Service | Enterprise Core | Assemble platform-level JSON, Markdown, CSV, and future HTML outputs from owned service data and published strategy outputs. | AI CIO, dashboards, notifications | Planned |
| Enterprise Investor Dashboard | AI CIO | Present cross-strategy allocations, health, risk, and recommendations. | Investor/operator | Existing Dividend-hosted integration classified for migration |
| AI CIO Recommendation Service | AI CIO | Produce cross-strategy recommendations using enterprise and strategy-published evidence. | Investor/operator | Planned |
| AI CIO Strategy Monitor | AI CIO | Monitor plugin status, health, readiness, and output freshness. | Investor/operator | Planned |
| AI CIO Allocation Intelligence | AI CIO | Recommend paper-capital allocations; execution remains governed by the Allocation Service. | Governance, investor/operator | Planned |

## Strategy Plugins

### Dividend Strategy

Owner: Trade-Dividend-Bot.

Owns:

- Dividend screening, ranking, quality, safety, growth, and income analysis.
- Dividend-specific portfolio lifecycle and simulated holdings.
- Dividend forecasts, payment calendars, alerts, reviews, learning, replacement analysis, and strategy health.
- Dividend strategy reports and recommendations.
- Independent Dividend runtime during migration.

Consumes:

- Enterprise Market Data API.
- Read-only paper cash and allocation contracts.
- Shared plugin and reporting contracts.

### Swing Strategy

Owner: Trade-Swing-Bot.

Owns:

- Opportunity quality, momentum, regime, confidence, entry, exit, and Strategy A/B logic.
- Swing paper positions, lifecycle, reentry cooldowns, and trade ledger.
- Swing strategy reports and recommendations.

Consumes:

- Enterprise Market Data API.
- Read-only paper cash and allocation contracts.
- Shared plugin and reporting contracts.

### Future Strategies

Options, Futures, Crypto, REIT, covered-call, and other strategies must register as independent paper-only plugins. They may not duplicate enterprise provider, cache, scheduling, governance, or paper-cash services.

## Service Interaction Rule

```text
Strategy request
    -> Enterprise API contract
    -> Enterprise-owned service
    -> normalized and validated response
    -> strategy-owned calculation
    -> published strategy artifacts
    -> AI CIO aggregation and recommendation
```

## Stage 1 Exit Requirement

This catalog is frozen only when each named service has:

1. One authoritative owner.
2. Defined consumers.
3. A migration status.
4. A corresponding API or artifact contract.
5. A paper-only safety boundary.
