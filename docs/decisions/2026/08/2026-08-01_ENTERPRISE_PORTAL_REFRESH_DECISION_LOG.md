# Enterprise Portal Consolidated Refresh Decision Log

## Decision ID

DEC-2026-08-01-PORTAL-REFRESH-001

## Date

2026-08-01

## Phase

Post-Phase 3.4 orchestration consolidation

## Status

Implemented; focused validation pending local test run.

## Approved Decision

The Enterprise portal will expose one operational refresh command:

```text
python refresh_enterprise_portal.py
```

This command runs the established base dashboard refresh first and then publishes the Phase 3 intelligence documents from those exact refreshed artifacts.

The lower-level commands remain available for diagnosis and isolated testing:

```text
python refresh_enterprise_dashboards.py
python publish_enterprise_dashboard_intelligence.py
```

## Reason

The existing base dashboard refresh has broad, stable test coverage. A thin orchestration layer provides one DigitalOcean service entry point without rewriting or destabilizing that tested implementation.

## Required Execution Order

1. Refresh Registry v2 evidence.
2. Build strategy discovery and normalized strategy KPIs.
3. Build Executive and Investor dashboard base documents.
4. Write the base dashboard artifacts.
5. Read those exact artifacts.
6. Build AI CIO interpretation, strategy comparison, and contributor details.
7. Attach one identical canonical intelligence payload to both dashboards.
8. Publish the separate Phase 3 intelligence artifacts.
9. Confirm strategy IDs remain identical across dashboard discovery and intelligence publication.

## Created Files

- `refresh_enterprise_portal.py`
- `tests/test_refresh_enterprise_portal.py`

## Safety Rules

- Paper trade mode remains required.
- Live trading remains disabled.
- Broker execution remains disabled.
- Capital movement remains disabled.
- The orchestration layer is read-only and reporting-only.
- No strategy, portfolio, allocation, governance, or recommendation calculations are changed.

## Failure Behavior

The combined refresh is not complete when:

- the base dashboard refresh reports errors;
- Phase 3 publication raises an exception;
- discovered strategy IDs and published intelligence strategy IDs differ.

Warnings do not silently disappear. Base-refresh and intelligence-publication warnings are merged into the combined summary.

## DigitalOcean Deployment Validation

The service command must create or update:

- `results/ai_cio_executive_dashboard.json`
- `results/enterprise_investor_dashboard.json`
- `results/enterprise_strategy_kpis.json`
- `results/enterprise_dashboard_intelligence.json`
- `results/enterprise_ai_cio_strategy_interpretation.json`
- `results/enterprise_strategy_comparison.json`
- `results/enterprise_contributor_details.json`

The Executive and Investor dashboard JSON documents must contain identical `enterprise_dashboard_intelligence` objects.

The combined command output must report:

- refresh completion status;
- registered strategy count;
- strategy IDs;
- artifact paths;
- warnings;
- errors.

## Current Strategy Scope

Current deployment validation focuses on:

- `DIVIDEND-001`
- `SWING-001`

The orchestration itself remains registry-driven and must not hardcode those strategy IDs.
