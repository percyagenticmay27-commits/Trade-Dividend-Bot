# AI CIO Strategy Integration Standard Version 1

## Purpose

This document is the authoritative onboarding and interoperability standard for every current and future bot, strategy, or analytical service that must operate under the Enterprise Trade Platform and be recognized by the AI CIO.

A strategy that follows this standard must be able to:

- register itself with the AI CIO;
- identify its capabilities and restrictions;
- consume approved enterprise services;
- publish health, status, outputs, and reports in a predictable format;
- remain independently runnable;
- preserve paper-only safety boundaries unless a separately approved execution architecture is introduced;
- be discovered and monitored without the AI CIO importing or recalculating the strategy's internal logic.

This standard applies to the Dividend strategy, Swing strategy, and all future strategies, including Options, Futures, Crypto, REIT, Covered Call, Wheel, Tax, or other strategy plugins.

## Governing Architecture

The Enterprise Trade Platform is the parent architecture.

```text
Enterprise Trade Platform
│
├── Enterprise Core Services
│   ├── Market Data
│   ├── Provider Priority
│   ├── Cache
│   ├── Validation
│   ├── Portfolio
│   ├── Governance
│   ├── Scheduler
│   ├── Reporting
│   ├── Notifications
│   └── Plugin Registry
│
├── AI CIO
│   ├── Strategy Monitoring
│   ├── Capital Allocation Recommendations
│   ├── Enterprise Health
│   ├── Executive Reporting
│   └── Cross-Strategy Governance
│
└── Strategy Plugins
    ├── Dividend
    ├── Swing
    └── Future Strategies
```

The AI CIO is not the owner of strategy calculations. It consumes strategy-published contracts and enterprise services.

## Permanent Separation of Responsibilities

### Enterprise Core owns

- provider selection;
- shared market data acquisition;
- market-data normalization;
- market-data validation;
- shared cache and fallback policy;
- enterprise portfolio cash and cross-strategy allocation state;
- strategy registration and discovery;
- enterprise scheduling;
- enterprise reporting aggregation;
- shared notifications;
- governance and approval workflows;
- enterprise health aggregation.

### AI CIO owns

- cross-strategy monitoring;
- enterprise-level recommendations;
- capital allocation recommendations and governance views;
- strategy readiness summaries;
- executive dashboards;
- enterprise analytics;
- risk and health escalation across strategies.

### Each strategy owns

- its investment philosophy;
- its scoring and ranking logic;
- its signal logic;
- its entry and exit rules;
- its strategy-specific paper state;
- its strategy-specific lifecycle;
- its strategy-specific reports;
- its own tests;
- its own independently runnable daily or periodic cycle.

The AI CIO must never duplicate or recalculate strategy-owned scores.

## Required Strategy Identity

Every strategy must have a stable identity that does not change between runs.

Required fields:

- `strategy_id`
- `strategy_name`
- `strategy_type`
- `strategy_class`
- `version`
- `schema_version`
- `lifecycle_status`
- `runtime_status`
- `paper_trade_mode`
- `live_trading_enabled`
- `broker_execution_enabled`
- `order_placement_enabled`

Recommended identifier format:

```text
DIVIDEND-001
SWING-001
OPTIONS-001
FUTURES-001
CRYPTO-001
```

The identifier must remain stable even if the display name changes.

## Required Directory Contract

Every strategy must publish or expose the following logical structure:

```text
strategy-root/
│
├── manifest.json
├── status.json
├── health.json
├── outputs.json
│
├── reports/
├── results/
├── logs/
├── state/
├── configs/
└── tests/
```

Physical paths may differ during migration, but the strategy must provide these artifacts through its declared plugin contract.

## Required Manifest Contract

`manifest.json` is the AI CIO's primary discovery document.

Minimum required structure:

```json
{
  "schema_version": "1.0",
  "strategy_id": "SWING-001",
  "strategy_name": "Trade Swing Bot",
  "strategy_type": "SWING",
  "strategy_class": "CAPITAL_GROWTH",
  "version": "1.0.0",
  "lifecycle_status": "PRODUCTION_PAPER",
  "paper_trade_mode": true,
  "live_trading_enabled": false,
  "broker_execution_enabled": false,
  "order_placement_enabled": false,
  "entrypoint": "python -m swing_trade_bot.daily_cycle",
  "health_path": "health.json",
  "status_path": "status.json",
  "outputs_path": "outputs.json",
  "reports_path": "reports",
  "results_path": "results",
  "logs_path": "logs",
  "state_path": "state",
  "supported_capabilities": [],
  "required_enterprise_services": [],
  "published_outputs": [],
  "permissions": {},
  "generated_at": "ISO-8601 UTC timestamp"
}
```

## Required Status Contract

`status.json` communicates operational state, not investment recommendations.

Required fields:

```json
{
  "schema_version": "1.0",
  "strategy_id": "SWING-001",
  "runtime_status": "ONLINE",
  "lifecycle_status": "PRODUCTION_PAPER",
  "last_run_started_at": "ISO-8601 UTC timestamp or null",
  "last_run_completed_at": "ISO-8601 UTC timestamp or null",
  "last_success_at": "ISO-8601 UTC timestamp or null",
  "last_failure_at": "ISO-8601 UTC timestamp or null",
  "run_count": 0,
  "success_count": 0,
  "failure_count": 0,
  "current_cycle_id": null,
  "message": "",
  "updated_at": "ISO-8601 UTC timestamp"
}
```

Allowed runtime states should include:

- `OFFLINE`
- `STARTING`
- `ONLINE`
- `RUNNING`
- `DEGRADED`
- `PAUSED`
- `ERROR`
- `STOPPED`

## Required Health Contract

`health.json` communicates whether the strategy is safe and operationally ready.

Minimum structure:

```json
{
  "schema_version": "1.0",
  "strategy_id": "SWING-001",
  "health_status": "OK",
  "health_score": 100,
  "paper_trade_mode": true,
  "required_files_present": true,
  "missing_required_files": [],
  "warnings": [],
  "errors": [],
  "dependencies": [],
  "last_successful_cycle_at": null,
  "checked_at": "ISO-8601 UTC timestamp"
}
```

Allowed health states:

- `OK`
- `WARNING`
- `ERROR`
- `UNKNOWN`

A strategy must not report `OK` if a required file, required service, or permanent safety rule is failing.

## Required Outputs Contract

`outputs.json` tells the AI CIO what the strategy produced and where it can be read.

Minimum structure:

```json
{
  "schema_version": "1.0",
  "strategy_id": "SWING-001",
  "output_count": 0,
  "report_files": [],
  "data_files": [],
  "state_summary_files": [],
  "log_files": [],
  "latest_report": null,
  "latest_data": null,
  "latest_health": "health.json",
  "latest_status": "status.json",
  "warnings": [],
  "generated_at": "ISO-8601 UTC timestamp"
}
```

The AI CIO reads these files. It does not infer paths by scanning arbitrary directories.

## Capability Declaration

Every strategy must explicitly declare the capabilities it provides and the enterprise services it consumes.

Example:

```json
{
  "supported_capabilities": [
    "opportunity_scoring",
    "entry_analysis",
    "exit_analysis",
    "paper_portfolio_management",
    "weekly_reporting"
  ],
  "required_enterprise_services": [
    "market_data.history",
    "market_data.quote",
    "portfolio.available_capital",
    "governance.allocation_requests",
    "reporting.publish"
  ]
}
```

Capabilities must describe what the strategy owns. They must not claim enterprise infrastructure as a strategy capability.

## Permissions Contract

Every strategy must use least-privilege permissions.

Example:

```json
{
  "permissions": {
    "market_data_read": true,
    "portfolio_read": true,
    "allocation_request_create": true,
    "strategy_state_write": true,
    "enterprise_cash_write": false,
    "broker_account_read": false,
    "broker_execution": false,
    "order_placement": false
  }
}
```

The AI CIO must reject registration when a strategy requests permissions outside the approved architecture.

## Registration Workflow

A new strategy must follow this sequence:

```text
1. Install strategy code
2. Validate configuration
3. Generate manifest.json
4. Generate status.json
5. Generate health.json
6. Generate outputs.json
7. Submit or expose registration metadata
8. AI CIO validates identity and schema
9. AI CIO validates safety flags
10. AI CIO validates required enterprise services
11. AI CIO registers the strategy
12. Strategy enters VALIDATED status
13. Paper acceptance tests run
14. Strategy enters PAPER_CERTIFIED status
15. Scheduler may enable recurring execution
```

Registration must fail closed. Missing or malformed required fields must not be silently defaulted to safe values.

## AI CIO Recognition Rules

The AI CIO recognizes a strategy only when all of the following are true:

- the `strategy_id` is unique;
- all required contract files exist;
- contract schemas are supported;
- safety flags are explicit and valid;
- the declared entrypoint exists or is callable;
- required enterprise services are available;
- health is not `ERROR`;
- permissions are approved;
- the strategy has passed the applicable paper acceptance checks;
- published output paths remain inside approved strategy or shared output roots.

Recognition is metadata-based. The AI CIO must not import private strategy modules to discover how the strategy works.

## Startup Handshake

At startup, a strategy should perform this handshake:

```text
Strategy starts
    ↓
Loads local configuration
    ↓
Validates permanent safety flags
    ↓
Checks Enterprise Core service availability
    ↓
Writes STARTING status
    ↓
Publishes health
    ↓
Registers or refreshes registration with AI CIO
    ↓
Receives registration acknowledgement
    ↓
Writes ONLINE status
```

If Enterprise Core is unavailable, the strategy may remain independently runnable only under a documented migration fallback. It must publish `DEGRADED` status and disclose the fallback source.

## Run Workflow

Every scheduled strategy cycle should follow this sequence:

```text
Scheduler authorizes cycle
    ↓
Strategy writes RUNNING status
    ↓
Strategy requests approved enterprise inputs
    ↓
Strategy validates input quality
    ↓
Strategy performs its own calculations
    ↓
Strategy updates strategy-owned paper state
    ↓
Strategy writes data and reports
    ↓
Strategy refreshes outputs.json
    ↓
Strategy refreshes health.json
    ↓
Strategy writes ONLINE or DEGRADED status
    ↓
AI CIO aggregates the published results
```

A strategy must never mark a run successful before its required state and output artifacts are durably written.

## Enterprise Market Data Rules

Strategies must consume market data through the Enterprise Market Data API.

Approved provider policy:

```text
YFINANCE
    ↓ failure
ROBINHOOD_READ_ONLY
    ↓ failure
VALID_PRIOR_CSV
```

Current Robinhood boundary:

- DigitalOcean Codex runtime is installed and authenticated;
- Robinhood MCP is authenticated;
- `get_equity_historicals` is the currently verified capability;
- Robinhood access is read-only;
- trading, order, balance, account, transfer, and position tools are unavailable;
- the MCP cleanup `DELETE` HTTP 400 after a successful retrieval is an operational cleanup issue, not a failed historical-data call.

Strategies must not:

- call Yahoo directly after Enterprise Market Data cutover;
- call Robinhood MCP directly;
- invoke Codex as a provider from strategy logic;
- choose provider priority;
- normalize provider-specific payloads;
- write to the shared enterprise cache.

The Enterprise Market Data Service returns a normalized contract that includes provider and quality metadata.

## Market Data Quality Handling

Strategies must recognize enterprise quality states:

- `VERIFIED`
- `PARTIAL`
- `STALE`
- `UNAVAILABLE`

Recommended behavior:

- `VERIFIED`: normal strategy processing;
- `PARTIAL`: process only when strategy requirements are satisfied and issue a warning;
- `STALE`: use only when the strategy explicitly permits stale evidence and disclose it;
- `UNAVAILABLE`: fail the affected calculation safely and publish degraded health.

Missing evidence must follow each strategy's frozen calculation rules. The AI CIO does not invent missing strategy evidence.

## Portfolio and Capital Rules

Enterprise-level cash and cross-strategy allocations belong to the Enterprise Portfolio and Governance services.

A strategy may:

- read available paper capital;
- read its approved paper allocation;
- submit an allocation request;
- read allocation decisions;
- maintain strategy-specific simulated holdings when that ownership is explicitly assigned.

A strategy may not:

- directly change enterprise cash;
- approve its own allocation request;
- move capital between strategies;
- overwrite another strategy's state;
- treat an allocation recommendation as broker execution authorization.

## State Ownership Rules

Every state artifact must have exactly one owner.

Examples:

- enterprise paper cash: Enterprise Portfolio Service;
- cross-strategy allocation ledger: Governance Service;
- Dividend lifecycle state: Dividend strategy;
- Swing open and closed paper positions: Swing strategy;
- market cache: Enterprise Market Data Service;
- AI CIO recommendations: AI CIO.

A consumer may read an owner's published contract but may not silently rewrite that state.

## Scheduling Rules

The long-term Enterprise Scheduler owns when strategies run.

Strategies must remain independently runnable for:

- testing;
- recovery;
- manual paper runs;
- migration rollback;
- service isolation.

A strategy must not create conflicting recurring schedules after Enterprise Scheduler cutover.

The schedule authority must be visible in the manifest or runtime configuration.

## Reporting Rules

A strategy calculates and publishes strategy-specific reports.

The Enterprise Reporting Service may:

- validate report metadata;
- index reports;
- aggregate summaries;
- render enterprise dashboards;
- deliver approved report packages.

It must not alter the strategy's calculations.

Recommended output formats:

- JSON for contracts and machine consumption;
- Markdown for human-readable reports;
- CSV for tabular exports;
- HTML only as a presentation derivative.

## Notification Rules

Strategies should publish notification-worthy events rather than directly controlling enterprise delivery.

Example events:

- `StrategyRunCompleted`
- `StrategyRunFailed`
- `HealthChanged`
- `ReportPublished`
- `AllocationRequested`
- `RiskThresholdExceeded`

During migration, an existing strategy-owned email implementation may remain active until the shared Notification Service is validated.

## Event Contract

Events should contain at least:

```json
{
  "event_id": "unique identifier",
  "event_type": "StrategyRunCompleted",
  "schema_version": "1.0",
  "strategy_id": "SWING-001",
  "cycle_id": "unique cycle identifier",
  "severity": "INFO",
  "occurred_at": "ISO-8601 UTC timestamp",
  "summary": "",
  "artifact_paths": [],
  "metadata": {}
}
```

Allowed severity levels:

- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

## Failure and Degraded-Mode Rules

A strategy must fail safely and publish the failure.

On failure it must:

1. preserve the last valid state;
2. avoid partial overwrite of required artifacts;
3. increment failure counters;
4. write `ERROR` or `DEGRADED` status;
5. record a concise error summary;
6. refresh health;
7. emit an error event when event publishing is available;
8. avoid any broker action.

Fallback behavior must always be visible. A strategy may not report normal health while silently using stale data or an unapproved local provider.

## Lifecycle States

Recommended strategy lifecycle states:

- `INSTALLED`
- `REGISTERED`
- `VALIDATED`
- `PAPER_CERTIFIED`
- `PRODUCTION_PAPER`
- `MAINTENANCE`
- `DEPRECATED`
- `ARCHIVED`

Lifecycle status is not runtime status. A `PRODUCTION_PAPER` strategy can temporarily have runtime status `ERROR`.

## Versioning and Compatibility

Each strategy must version independently using semantic versioning.

It must also declare the versions of contracts it supports.

Example:

```json
{
  "version": "1.2.0",
  "supported_contract_versions": {
    "plugin": "1.x",
    "market_data": "1.x",
    "portfolio": "1.x",
    "governance": "1.x"
  }
}
```

A breaking contract change requires a new major version and an explicit migration path.

## Testing Requirements

Before registration as `PAPER_CERTIFIED`, a strategy must prove:

- manifest validation;
- status validation;
- health validation;
- outputs validation;
- unique and stable strategy identity;
- safety flags cannot be disabled accidentally;
- missing required files cause failure;
- malformed contracts cause failure;
- enterprise service outage produces safe degraded behavior;
- provider fallback metadata is preserved;
- stale data is disclosed;
- state writes are atomic or recoverable;
- repeated runs are deterministic where expected;
- reports and machine-readable outputs agree;
- no broker execution path exists in the strategy package;
- no unauthorized enterprise-state write exists;
- the strategy remains independently runnable.

## Paper-Only Safety Boundary

Until a separate execution architecture is explicitly designed, approved, isolated, and certified, every strategy must enforce:

```text
paper_trade_mode=True
live_trading_enabled=False
broker_execution_enabled=False
order_placement_enabled=False
```

Forbidden within strategy modules:

- placing orders;
- cancelling orders;
- modifying orders;
- transferring funds;
- changing brokerage positions;
- accessing or using credentials for execution;
- treating read-only Robinhood connectivity as execution permission.

Read-only market-data connectivity does not weaken the paper-only boundary.

## Minimum Onboarding Checklist

A future bot or strategy is ready to integrate only when all items are complete:

- [ ] Stable `strategy_id` assigned
- [ ] Strategy ownership and purpose documented
- [ ] `manifest.json` implemented
- [ ] `status.json` implemented
- [ ] `health.json` implemented
- [ ] `outputs.json` implemented
- [ ] Required enterprise services declared
- [ ] Capabilities declared
- [ ] Permissions declared
- [ ] Entrypoint documented and tested
- [ ] Strategy-owned state identified
- [ ] Enterprise-owned state excluded from direct writes
- [ ] Market data consumed through Enterprise Market Data API
- [ ] Provider-specific code excluded from strategy logic
- [ ] Reporting outputs indexed in `outputs.json`
- [ ] Failure and degraded modes tested
- [ ] Paper-only controls statically and dynamically tested
- [ ] Contract schema tests pass
- [ ] Independent manual run passes
- [ ] AI CIO registration validation passes
- [ ] Paper acceptance suite passes
- [ ] Scheduler integration tested
- [ ] AI CIO dashboard recognizes the strategy

## Instructions to Give a Future Bot

A project owner may give the following directive to any future bot or strategy implementation:

```text
Read docs/AI_CIO_STRATEGY_INTEGRATION_STANDARD_V1.md and implement the required AI CIO plugin contract without changing your strategy calculations.

Create and validate manifest.json, status.json, health.json, and outputs.json.

Declare your stable strategy identity, capabilities, required enterprise services, permissions, entrypoint, output paths, and state ownership.

Consume market data only through the Enterprise Market Data API. Do not call Yahoo, Codex, Robinhood MCP, or shared cache directly.

Remain independently runnable, preserve paper-only restrictions, publish health and status on every cycle, and pass the onboarding checklist before requesting AI CIO registration.
```

## Swing Strategy Application

The Swing Bot should use this standard to:

- identify itself with a stable ID such as `SWING-001`;
- publish its opportunity, market-regime, momentum, technical, entry, exit, and paper-portfolio capabilities;
- declare the Enterprise Market Data API as its market-data dependency;
- preserve its own paper position and lifecycle state;
- request but never self-approve enterprise capital allocations;
- publish normalized reports and output locations;
- register with the AI CIO without exposing private implementation details;
- remain paper-only and independently runnable.

The AI CIO recognizes the Swing Bot through its contracts, not by importing Swing Bot source code.

## Authority

This document is the permanent default integration standard for future strategies under Enterprise Trade Platform Version 1.

Strategy-specific freeze documents may impose additional restrictions but may not weaken these safety, ownership, registration, or interoperability requirements.

Any exception must be explicitly documented, versioned, reviewed, and approved before implementation.
