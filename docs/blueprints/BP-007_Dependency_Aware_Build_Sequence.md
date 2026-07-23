# BP-007 Dependency-Aware Build Sequence

**Version:** 1.0.0  
**Status:** FROZEN

## Purpose

Define the mandatory construction order for evolving the existing Trade-Dividend-Bot repository into the shared paper-only Investment Intelligence Platform without breaking current Dividend behavior.

## Build Principles

- Reuse and classify existing modules before creating replacements.
- Preserve public behavior until a tested migration is complete.
- Build lower-level dependencies before higher-level consumers.
- Add tests in the same implementation batch as code.
- Do not begin cloud deployment until release validation passes.

## Sequence

### Stage 0 — Repository Baseline

1. Repository hygiene and branch protection.
2. Repository classification matrix.
3. Blueprint and ADR freeze.
4. Baseline compilation and test inventory.

**Gate:** Architecture and current failures are documented.

### Stage 1 — Platform Foundation

1. Shared platform configuration.
2. Paper-only policy enforcement.
3. Identifier generation.
4. Version registry.
5. Shared validation, serialization, paths, logging, and diagnostics.

**Gate:** Foundation imports no strategy modules and passes independent tests.

### Stage 2 — Canonical Business Entities

1. Company identity.
2. Master Company Intelligence Profile.
3. Evidence records and append entries.
4. Strategy metadata and evaluation.
5. Decision and investor override.
6. Portfolio, position, lot, report, audit, and learning records.

**Gate:** Entities validate, serialize deterministically, and map to PostgreSQL-compatible schemas.

### Stage 3 — Evidence and Company Intelligence

1. Append-only evidence repository.
2. Company registry and MCIP repository.
3. Adapters for existing discovery, fundamental, growth, income, risk, technical, market, earnings, theme, and watchlist modules.
4. Snapshot and source lineage support.

**Gate:** Shared intelligence contains no strategy decision logic.

### Stage 4 — AI CIO Governance

1. Constitution enforcement.
2. Committee contribution model.
3. Decision ledger and lifecycle.
4. Investor override service.
5. Decision stability and supersession integration.

**Gate:** Exactly one automated decision authority exists and original decisions remain immutable.

### Stage 5 — Portfolio Platform

1. Consolidated paper portfolio.
2. Strategy-attributed positions and lots.
3. Allocation and lifecycle adapters.
4. Wealth attribution by strategy and period.

**Gate:** Dividend and future strategy returns can be reported independently while consolidated holdings remain accurate.

### Stage 6 — Strategy Framework

1. Strategy interface and metadata.
2. Strategy registry.
3. Lifecycle and configuration validation.
4. Strategy-scoped recommendation, report, audit, and learning contracts.

**Gate:** A sample strategy can register and run without changing platform modules.

### Stage 7 — Dividend Strategy Package

1. Wrap existing Dividend engines rather than rewrite them.
2. Isolate Dividend policy, ranking, income, allocation, exit, and re-entry behavior.
3. Produce Dividend-only daily, weekly, monthly, performance, learning, and audit outputs.
4. Preserve existing paper-cycle entry points during migration.

**Gate:** Existing Dividend outputs and new strategy-scoped outputs reconcile.

### Stage 8 — Reporting, Audit, and Learning Integration

1. Shared report model and renderers.
2. Shared audit model and renderers.
3. Strategy-isolated workspaces and archives.
4. Learning attribution and policy-change workflow.

**Gate:** No mixed strategy performance or decisions appear in strategy reports.

### Stage 9 — End-to-End Validation

1. Full syntax compilation.
2. Unit tests.
3. Integration tests.
4. End-to-end paper cycle.
5. Data integrity, report, audit, governance, and security checks.
6. Regression comparison with the existing Dividend Bot.

**Gate:** All release-blocking checks pass or have formally approved waivers.

### Stage 10 — Cloud Deployment

1. Externalized configuration and secrets.
2. Deployment package and launcher.
3. Health checks and smoke tests.
4. Scheduled paper cycle.
5. Report delivery validation.
6. Rollback procedure.

**Gate:** Cloud paper cycle completes successfully and no live execution capability is enabled.

### Stage 11 — Version 1 Freeze

Freeze Platform 1.0, Dividend Strategy 1.0, blueprint set, ADR set, schema, tests, and deployment runbook.

## Deferred Work

Swing, Options, real-time streaming, real broker execution, and multi-broker support are not required for Platform Version 1.0.

## Freeze Statement

This build sequence is mandatory for Version 1.0. Reordering requires an approved ADR with dependency and regression analysis.