# AI CIO Extraction Map

## Purpose

Stage 1 inventories and classifies the current Trade-Dividend-Bot architecture before any code is copied, moved, deprecated, or removed.

The target architecture keeps the Dividend strategy independent while extracting reusable enterprise services into the existing AI CIO containment.

This stage makes no production-code changes.

## Permanent Safety Boundary

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- `order_placement_enabled=False`
- No Robinhood execution
- No brokerage execution
- No real capital movement

## Classification Labels

- `KEEP_IN_DIVIDEND` — Dividend-specific strategy, lifecycle, analytics, state, or reporting responsibility.
- `MOVE_TO_AI_CIO` — Enterprise responsibility that should ultimately be owned by the AI CIO.
- `COPY_THEN_DEPRECATE` — Copy into AI CIO first, retain the working Dividend implementation during migration, and deprecate only after successful server validation.
- `SHARED_CONTRACT` — A schema, client boundary, manifest, status, health, or report contract shared by the AI CIO and strategy plugins.
- `UNDECIDED` — Requires a separate ownership decision before migration.

## Current Repository Role

The repository is currently a paper-only Dividend platform containing both:

1. Dividend-specific strategy capabilities.
2. Enterprise/platform capabilities that grew around the Dividend strategy.

The migration must separate these responsibilities without rebuilding the Dividend strategy or breaking the deployed DigitalOcean workflow.

## Preliminary Architecture Map

### Market Data

| File or capability | Classification | Target responsibility | Migration rule |
|---|---|---|---|
| `yahoo_finance_provider.py` | `COPY_THEN_DEPRECATE` | AI CIO provider layer | Copy to AI CIO. Keep local Dividend fallback until shared API is proven. |
| `market_data_provider.py` / `MarketDataService` | `COPY_THEN_DEPRECATE` | AI CIO Enterprise Market Data Service | Preserve current Dividend service during transition. |
| `market_data_cache.py` | `COPY_THEN_DEPRECATE` | AI CIO shared cache | Do not remove Dividend cache before rollback validation. |
| `market_data_integration_engine.py` | `UNDECIDED` | Split between enterprise acquisition and Dividend-specific snapshot requirements | Review consumers before deciding whether to split or retain an adapter. |
| `robinhood_agent_provider.py` on the open feature branch | `MOVE_TO_AI_CIO` | AI CIO read-only provider fallback | Do not merge into Dividend `main` as permanent ownership before AI CIO extraction is designed. |
| Provider priority logic | `MOVE_TO_AI_CIO` | AI CIO: Yahoo → Robinhood read-only → shared cache | Strategies must receive normalized results without choosing providers. |
| OHLCV normalization and validation | `MOVE_TO_AI_CIO` | AI CIO shared validator | Strategy-specific minimum-history rules remain in each strategy. |
| Dividend payment/event retrieval | `UNDECIDED` | Likely enterprise evidence service with Dividend-specific interpretation | Robinhood OHLCV cannot replace dividend-event evidence. |

### Dividend Strategy Intelligence

| Capability | Classification | Target responsibility |
|---|---|---|
| Dividend screening and rankings | `KEEP_IN_DIVIDEND` | Dividend strategy |
| Dividend safety, cuts, suspensions, consistency, coverage, yield, and growth analysis | `KEEP_IN_DIVIDEND` | Dividend strategy |
| Opportunity pairing and Dividend-specific selection | `KEEP_IN_DIVIDEND` | Dividend strategy |
| Dividend portfolio lifecycle and review rules | `KEEP_IN_DIVIDEND` | Dividend strategy |
| Dividend income forecasts and calendars | `KEEP_IN_DIVIDEND` | Dividend strategy |
| Dividend strategy dashboard | `KEEP_IN_DIVIDEND` | Dividend strategy |
| Dividend-specific reports and recommendations | `KEEP_IN_DIVIDEND` | Dividend strategy |

### Enterprise AI CIO and Plugin Capabilities

| Capability | Classification | Target responsibility |
|---|---|---|
| Enterprise AI CIO portal | `MOVE_TO_AI_CIO` | Platform navigation, health, readiness, approvals, and links |
| Enterprise service registry | `MOVE_TO_AI_CIO` | Strategy and service discovery |
| Plugin discovery | `MOVE_TO_AI_CIO` | Registry metadata only |
| Bot manifest, status, health, outputs, diagnostics, and readiness contracts | `SHARED_CONTRACT` | AI CIO owns validation and aggregation; each strategy publishes its own artifacts |
| Cross-strategy allocation governance | `MOVE_TO_AI_CIO` | AI CIO governance |
| Enterprise dashboard summaries | `MOVE_TO_AI_CIO` | AI CIO enterprise reporting |
| Dividend strategy dashboard | `KEEP_IN_DIVIDEND` | Dividend analytics only |
| Investor dashboard | `UNDECIDED` | Determine whether it is platform-wide or Dividend-only before movement |
| Executive dashboard | `UNDECIDED` | Split enterprise summary from Dividend-specific summary if both are currently combined |

### Paper Cash, Allocation, and State

| Capability | Classification | Target responsibility | Notes |
|---|---|---|---|
| Persistent paper cash account | `UNDECIDED` | Candidate AI CIO portfolio service | Current deployment must remain functional during migration. |
| Paper cash transaction ledger | `UNDECIDED` | Candidate AI CIO portfolio service | Preserve append-only history. |
| Paper allocation request ledger | `MOVE_TO_AI_CIO` | AI CIO governance | Strategies should not govern cross-strategy allocations. |
| Dividend paper portfolio state | `KEEP_IN_DIVIDEND` | Dividend strategy | Strategy owns its simulated holdings and Dividend lifecycle until a separately approved portfolio-service migration. |
| Future Swing paper portfolio state | Not in this repository | Swing strategy | Must not be stored in the Dividend repository. |

### Scheduling, Runtime, and Delivery

| Capability | Classification | Target responsibility |
|---|---|---|
| Current `dividend-bot.service` and Dividend daily launcher | `KEEP_IN_DIVIDEND` | Dividend runtime during migration |
| Future enterprise scheduler | `MOVE_TO_AI_CIO` | AI CIO orchestration, after strategy services remain independently runnable |
| SendGrid Dividend report delivery | `KEEP_IN_DIVIDEND` initially | Dividend operational delivery |
| Shared enterprise notifications | `UNDECIDED` | May later move to AI CIO after current delivery remains stable |
| Logs and operational health | `SHARED_CONTRACT` | Each service owns logs; AI CIO aggregates health and status |

### Compatibility Files and Tests

| Capability | Classification | Migration rule |
|---|---|---|
| `src/dividend_bot/` production modules | Mixed | Classify file by file; do not move the package wholesale. |
| Root-level compatibility copies | `KEEP_IN_DIVIDEND` during migration | Preserve existing deployment and test commands. |
| Dividend unit tests | `KEEP_IN_DIVIDEND` | Continue proving unchanged Dividend behavior. |
| Market-data provider/cache tests | `COPY_THEN_DEPRECATE` | Copy and adapt for AI CIO; retain Dividend regression coverage during transition. |
| Enterprise registry/governance tests | `MOVE_TO_AI_CIO` | Recreate against the AI CIO package and contracts. |
| Freeze and release documents | `SHARED_CONTRACT` or historical | Preserve history; add superseding migration documents rather than rewriting history. |

## Frozen Ownership Rules Already Supported by the Repository

The existing dashboard and workflow scope freeze establishes these useful boundaries:

- The Enterprise AI CIO Portal is platform-level navigation and status only.
- The Dividend Strategy Dashboard owns Dividend-specific analytics.
- Future strategies must own separate dashboards.
- Plugin discovery is registry metadata only.
- Values must be calculated once by their owning service and consumed by dashboards rather than recalculated.

These rules remain valid during extraction.

## Target End State

```text
AI CIO
  Enterprise Market Data API
    Provider Priority Engine
      Yahoo
      Robinhood Read-Only
      Shared Cache
    Normalized Data Contract
  Plugin Registry
  Governance and Allocation
  Enterprise Health and Reporting

Dividend Bot
  Dividend Strategy Logic
  Dividend Portfolio State
  Dividend Reports and Dashboard
  AI CIO Client
  Plugin Manifest, Status, Health, and Outputs

Swing Bot
  Swing Strategy Logic
  Persistent Swing Paper State
  Swing Reports and Dashboard
  AI CIO Client
  Plugin Manifest, Status, Health, and Outputs
```

## Stage 1 Deliverables

- [x] Create a dedicated Stage 1 branch.
- [x] Establish classification labels.
- [x] Record preliminary ownership boundaries.
- [x] Preserve all production code unchanged.
- [ ] Generate an exhaustive file inventory from the current repository tree.
- [ ] Assign one classification to every production module, launcher, configuration, state artifact, report generator, dashboard, test, and documentation file.
- [ ] Identify imports and runtime dependencies between enterprise and Dividend-specific modules.
- [ ] Identify which files are active on DigitalOcean versus historical or compatibility-only.
- [ ] Resolve all `UNDECIDED` entries before Stage 2.

## Stage 1 Exit Criteria

Stage 1 is complete only when:

1. Every relevant repository file is classified.
2. No production code has been moved or deleted.
3. Existing DigitalOcean behavior remains unchanged.
4. Enterprise-to-strategy boundaries are documented.
5. Rollback and compatibility requirements are documented.
6. The AI CIO repository and deployed path are identified as the single extraction target.
7. The extraction map is reviewed and approved before Stage 2 begins.

## Explicit Non-Goals

Stage 1 does not:

- create the Enterprise Market Data API;
- modify the current Dividend market-data provider;
- merge the Robinhood fallback into production;
- migrate paper cash or portfolio state;
- alter systemd services;
- connect the Swing strategy;
- remove compatibility files;
- enable live trading or broker execution.
