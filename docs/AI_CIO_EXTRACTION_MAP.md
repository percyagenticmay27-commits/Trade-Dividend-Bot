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

## Validated File Inventory from Repository History

The following inventory is derived from the current repository structure documented in the README and the merged Platform V1 pull-request history. Root-level compatibility wrappers follow the same ownership as their corresponding `src/dividend_bot/` implementation but remain in place during migration.

### Enterprise and Cross-Strategy Modules

| Production file | Compatibility file | Classification | Target |
|---|---|---|---|
| `src/dividend_bot/enterprise_dividend_service_registry_event_wiring.py` | `enterprise_dividend_service_registry_event_wiring.py` | `MOVE_TO_AI_CIO` | AI CIO plugin/service registry and event routing. Dividend-specific registry entries become plugin-published metadata. |
| `src/dividend_bot/paper_capital_allocation.py` | `paper_capital_allocation.py` | `MOVE_TO_AI_CIO` | AI CIO allocation governance and request ledger. |
| `src/dividend_bot/paper_capital_allocation_server.py` | `paper_capital_allocation_server.py` | `MOVE_TO_AI_CIO` | AI CIO allocation workflow UI/API. |
| `src/dividend_bot/enterprise_investor_dashboard_integration.py` | `enterprise_investor_dashboard_integration.py` | `MOVE_TO_AI_CIO` | Platform-wide investor view after Dividend-only fields are supplied through the strategy contract. |
| `src/dividend_bot/platform_v1_release.py` | `platform_v1_release.py` | `SHARED_CONTRACT` | Historical Dividend Platform V1 release gate; future enterprise release gate belongs in AI CIO. Preserve this file unchanged as release history. |
| `src/dividend_bot/cloud_readiness.py` | `cloud_readiness.py` | `SHARED_CONTRACT` | Each strategy publishes readiness; AI CIO aggregates enterprise readiness. Dividend deployment checks remain local. |
| `src/dividend_bot/paper_production_acceptance.py` | `paper_production_acceptance.py` | `SHARED_CONTRACT` | Dividend acceptance remains local; AI CIO later owns cross-service acceptance orchestration. |

### Dividend-Owned Strategy and Advisory Modules

Although several filenames begin with `enterprise_dividend_`, their calculations and evidence are Dividend-specific. They remain in the Dividend strategy; only normalized outputs and shared schemas are exposed to AI CIO.

| Production file | Compatibility file | Classification | Reason |
|---|---|---|---|
| `src/dividend_bot/enterprise_dividend_alert_integration.py` | `enterprise_dividend_alert_integration.py` | `KEEP_IN_DIVIDEND` | Converts Dividend evidence into Dividend-specific governed alerts. |
| `src/dividend_bot/enterprise_dividend_review_workflow.py` | `enterprise_dividend_review_workflow.py` | `KEEP_IN_DIVIDEND` | Owns Dividend alert-review lifecycle and traceability. |
| `src/dividend_bot/enterprise_dividend_learning_integration.py` | `enterprise_dividend_learning_integration.py` | `KEEP_IN_DIVIDEND` | Learns from Dividend forecasts, payments, alerts, and review outcomes. |
| `src/dividend_bot/enterprise_dividend_cio_advisory_integration.py` | `enterprise_dividend_cio_advisory_integration.py` | `KEEP_IN_DIVIDEND` | Produces Dividend strategy recommendations; AI CIO consumes but does not recalculate them. |
| `src/dividend_bot/enterprise_dividend_replacement_integration.py` | `enterprise_dividend_replacement_integration.py` | `KEEP_IN_DIVIDEND` | Compares Dividend holdings and Dividend replacement candidates. |
| `src/dividend_bot/enterprise_dividend_strategy_health_integration.py` | `enterprise_dividend_strategy_health_integration.py` | `KEEP_IN_DIVIDEND` | Measures Dividend strategy health. AI CIO aggregates the published health artifact. |
| `src/dividend_bot/enterprise_dividend_daily_cycle_integration.py` | `enterprise_dividend_daily_cycle_integration.py` | `KEEP_IN_DIVIDEND` initially | Dividend cycle orchestration stays independently runnable. AI CIO later schedules the cycle externally rather than absorbing its calculations. |

### Runtime and Launcher Files

| File | Classification | Migration rule |
|---|---|---|
| `start_dividend_bot.sh` | `KEEP_IN_DIVIDEND` | Preserve DigitalOcean startup behavior. |
| `start_dividend_bot.cmd` | `KEEP_IN_DIVIDEND` | Preserve Windows/Git CMD compatibility. |
| Current daily paper-cycle launcher | `KEEP_IN_DIVIDEND` | AI CIO may schedule it later, but the Dividend service must remain independently runnable. |
| Current SendGrid report-delivery implementation | `KEEP_IN_DIVIDEND` initially | Do not centralize until delivery stability and message ownership are reviewed. |

### Persistent State Artifacts

| Artifact | Classification | Decision |
|---|---|---|
| `state/paper_cash_account.json` | `MOVE_TO_AI_CIO` | Cash is enterprise-level and must support multiple strategies. Migrate only after an append-only import and rollback plan exists. |
| `state/paper_cash_transactions.jsonl` | `MOVE_TO_AI_CIO` | Enterprise cash ledger; preserve IDs, ordering, timestamps, and immutable history. |
| `state/paper_allocation_requests.jsonl` | `MOVE_TO_AI_CIO` | Cross-strategy governance ledger. |
| Dividend holdings, Dividend lifecycle, Dividend payment, Dividend forecast, and Dividend review state | `KEEP_IN_DIVIDEND` | Strategy-owned state. AI CIO receives read-only summaries through contracts. |

### Tests

| Test file or family | Classification | Rule |
|---|---|---|
| `tests/test_enterprise_dividend_service_registry_event_wiring.py` | `MOVE_TO_AI_CIO` plus Dividend contract regression | Recreate enterprise registry tests in AI CIO; retain tests proving Dividend publishes valid metadata. |
| `tests/test_paper_capital_allocation.py` | `MOVE_TO_AI_CIO` | Allocation workflow is enterprise governance. |
| `tests/test_enterprise_investor_dashboard_integration.py` | `MOVE_TO_AI_CIO` with Dividend fixture contract | Dashboard becomes enterprise-owned. |
| `tests/test_cloud_readiness.py` | `SHARED_CONTRACT` | Split into local Dividend readiness and enterprise aggregation coverage. |
| `tests/test_paper_production_acceptance.py` | `SHARED_CONTRACT` | Preserve Dividend acceptance; add AI CIO end-to-end acceptance later. |
| `tests/test_platform_v1_release.py` | Historical / `SHARED_CONTRACT` | Preserve as Platform V1 evidence. |
| `tests/test_dashboard_and_workflow_scope_freeze.py` | Historical / `SHARED_CONTRACT` | Preserve frozen ownership rules. |
| `tests/test_end_to_end_dividend_integration.py` | `KEEP_IN_DIVIDEND` | Continues proving the complete Dividend strategy workflow. |
| Alert, review, learning, advisory, replacement, strategy-health, and daily-cycle tests | `KEEP_IN_DIVIDEND` | These validate Dividend-specific behavior. |
| Market-data provider, cache, normalization, and provider fallback tests | `COPY_THEN_DEPRECATE` | Copy into AI CIO and retain Dividend regression tests until cutover. |

### Documentation

| File | Classification | Rule |
|---|---|---|
| `docs/DASHBOARD_AND_WORKFLOW_SCOPE_FREEZE.md` | `SHARED_CONTRACT` | Permanent ownership boundary and migration input. |
| `docs/PLATFORM_V1_RELEASE.md` | Historical | Preserve unchanged. |
| `docs/PLATFORM_V1_DIVIDEND_FREEZE.md` | Historical | Preserve unchanged. |
| `docs/PAPER_CAPITAL_ALLOCATION_UI.md` | `MOVE_TO_AI_CIO` conceptually | Preserve original history; create a successor AI CIO document rather than moving history. |
| `docs/PAPER_PRODUCTION_ACCEPTANCE_TEST.md` | `SHARED_CONTRACT` | Dividend acceptance remains valid; enterprise acceptance is additive. |
| `docs/CLOUD_READINESS_AND_DIGITALOCEAN_DEPLOYMENT.md` | `SHARED_CONTRACT` | Split future documentation into Dividend service deployment and AI CIO deployment. |
| `docs/MASTER_DEVELOPMENT_ROADMAP.md` | Historical / mixed | Preserve; future enterprise roadmap belongs in AI CIO. |
| `docs/AI_CIO_EXTRACTION_MAP.md` | `SHARED_CONTRACT` | Governs this migration. |

## Resolved Ownership Decisions

The following preliminary `UNDECIDED` items are now resolved:

1. **Investor dashboard:** `MOVE_TO_AI_CIO`. It is platform-wide and must combine multiple strategy summaries without reproducing strategy calculations.
2. **Persistent paper cash account:** `MOVE_TO_AI_CIO`. Cash must support multiple independently allocated strategies.
3. **Paper cash transaction ledger:** `MOVE_TO_AI_CIO`. It is the enterprise source of truth for simulated funding.
4. **Executive dashboard:** split ownership. The enterprise executive summary moves to AI CIO; Dividend-only executive analytics remain a Dividend report or dashboard section.
5. **Shared notifications:** remain `UNDECIDED` until SendGrid ownership, recipient policy, and cross-strategy notification requirements are inventoried.
6. **Market-data integration engine:** remains `UNDECIDED` until its imports and consumers are inspected directly.
7. **Dividend event retrieval:** remains `UNDECIDED` pending a source and normalized corporate-action contract review.

## Dependency Boundaries Identified

### AI CIO may call or read

- strategy manifest, status, health, outputs, readiness, and capabilities;
- normalized strategy reports and dashboard links;
- paper cash and allocation governance records after migration;
- strategy cycle launch command or service endpoint;
- shared market-data provider and cache services after Stage 2.

### AI CIO must not import

- Dividend scoring or ranking functions;
- Dividend alert, review, replacement, or lifecycle calculations;
- Dividend portfolio mutation logic;
- Dividend forecast or income calculation internals;
- root-level compatibility wrappers as an enterprise dependency.

### Dividend Bot may call

- AI CIO Enterprise Market Data API;
- AI CIO cash/allocation read contract;
- AI CIO plugin registration and heartbeat contract;
- AI CIO governance request contract.

### Dividend Bot must continue to own

- its independent runtime and failure isolation;
- Dividend holdings and lifecycle state;
- strategy calculations and recommendations;
- strategy-specific reports, alerts, reviews, learning, and health;
- rollback-compatible local market data during migration.

## DigitalOcean Activity Classification

The following files are treated as active until server verification proves otherwise:

- Linux startup launcher and the command used by `dividend-bot.service`;
- daily paper-cycle entry point;
- current market-data provider and cache;
- persistent `state/` cash and allocation files;
- report generation used by scheduled delivery;
- SendGrid delivery implementation;
- cloud-readiness and acceptance artifacts used for deployment validation.

Root-level Python compatibility files are classified as compatibility-active because existing commands and service scripts may still reference them. They must not be removed during Stage 1 or Stage 2.

A direct server-to-repository path audit is still required to distinguish active files from historical files conclusively.

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
- [x] Build a validated inventory from the README and merged Platform V1 pull-request history.
- [x] Classify all production modules introduced in Platform V1 Phases 2 through 15.
- [x] Classify known launchers, persistent cash/allocation state, major tests, and migration documents.
- [x] Resolve investor dashboard, paper cash, paper cash ledger, allocation, and executive dashboard ownership.
- [x] Identify enterprise-to-strategy dependency boundaries.
- [ ] Complete a direct recursive repository-tree inventory for files predating the GitHub Platform V1 phase history.
- [ ] Inspect imports and consumers of `market_data_integration_engine.py`.
- [ ] Inventory corporate-action and dividend-event data sources and schemas.
- [ ] Verify exact DigitalOcean service commands and active paths against the repository.
- [ ] Decide shared notification ownership.
- [ ] Identify the exact AI CIO repository name and deployed path as the single extraction target.

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
