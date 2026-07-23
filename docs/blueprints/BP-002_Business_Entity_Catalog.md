# BP-002 — Business Entity Catalog

**Version:** 1.0.0  
**Status:** FROZEN  
**Applies to:** Shared platform, Dividend Strategy, and future strategy packages

## 1. Purpose

This catalog defines the canonical business entities used by the platform. It establishes ownership boundaries so shared intelligence is implemented once while every strategy retains independent decisions, reports, audits, performance, and learning.

## 2. Identity Standard

Every persistent business entity must use dual identifiers:

- an internal UUID for durable relationships;
- a human-friendly identifier for reports, support, audits, and investor review.

Human-friendly examples:

- `CMP-2026-000001`
- `MCIP-2026-000001`
- `EVR-2026-000001`
- `DEC-2026-000001`
- `STR-2026-000001`
- `RPT-2026-000001`
- `AUD-2026-000001`
- `LRN-2026-000001`

## 3. Shared Platform Entities

### 3.1 Company

Canonical identity for a publicly traded company or issuer.

Key responsibilities:

- symbol and exchange identity;
- legal and display names;
- sector and industry classification;
- active, delisted, merged, or archived status;
- relationship to exactly one current Master Company Intelligence Profile.

### 3.2 Asset

Tradable paper instrument associated with a company, fund, ETF, leveraged ETF, or other supported instrument.

Key responsibilities:

- ticker and instrument type;
- underlying company or benchmark relationship;
- leverage factor when applicable;
- currency and exchange;
- lifecycle status.

### 3.3 Master Company Intelligence Profile

The single source of truth for company intelligence. Exactly one logical profile exists per company.

Contains or references:

- identity;
- discovery;
- fundamentals;
- growth;
- income;
- financial health;
- risk;
- technical calculations;
- market intelligence;
- themes;
- earnings;
- watchlist intelligence;
- evidence timeline;
- learning history;
- refresh and quality metadata.

It must not contain strategy decisions, strategy entries, strategy exits, or strategy allocations.

### 3.4 Intelligence Snapshot

Immutable dated representation of computed intelligence at a point in time.

Used for:

- historical comparison;
- audit reconstruction;
- simulation;
- walk-forward analysis;
- decision explanation;
- learning.

### 3.5 Evidence Record

Canonical evidence item associated with a company, asset, decision, policy, or platform event.

Evidence is append-only and must preserve source, timestamp, type, quality, and provenance.

### 3.6 Evidence Append Entry

A new entry extending an Evidence Record without replacing prior content.

Examples include corrections, follow-ups, official responses, regulatory updates, market reactions, committee requests, investor notes, and final resolutions.

### 3.7 Theme

Shared market, industry, macroeconomic, or investment theme.

Examples:

- semiconductor demand;
- artificial intelligence infrastructure;
- defensive income;
- interest-rate sensitivity.

### 3.8 Watchlist

Platform-level collection of companies or assets under observation.

A Watchlist may be shared, but strategy-specific watchlist evaluations must remain attributed to the strategy that produced them.

### 3.9 Market Event

Material event such as earnings, guidance, analyst action, regulatory action, corporate action, macro release, or unusual market movement.

### 3.10 Platform Configuration

Read-only runtime configuration controlling paths, schedules, feature availability, environment, and paper-only enforcement.

### 3.11 Platform Service Registration

Registry record describing an available shared service, its version, status, dependencies, and health.

## 4. Governance Entities

### 4.1 AI CIO Decision

The only automated final investment decision entity.

Contains:

- decision scope;
- strategy attribution;
- paper action;
- rationale;
- confidence;
- risks;
- evidence references;
- committee references;
- constitutional version;
- lifecycle state;
- supersession and override links.

### 4.2 Committee

Registered analytical committee with a defined mandate.

A Committee analyzes and recommends but never decides.

### 4.3 Committee Finding

Immutable committee output containing analysis, score, questions, conflicts, uncertainty, and recommendation.

### 4.4 Investor

Authorized human actor permitted to approve, request review, or override an AI CIO decision.

### 4.5 Investor Override

Historical record that preserves the original AI CIO decision and records the investor-directed replacement instruction and reason.

### 4.6 Policy

Versioned governance or strategy rule applied during evaluation.

### 4.7 Constitution Version

Versioned record identifying the AI CIO Constitution used for a decision.

## 5. Strategy Framework Entities

### 5.1 Strategy Definition

Canonical registered strategy package.

Contains:

- strategy identifier;
- name;
- version;
- lifecycle status;
- supported assets;
- required intelligence;
- supported report types;
- supported audit types;
- paper-only capability;
- module entry points.

### 5.2 Strategy Configuration

Versioned strategy-specific parameters and policies.

Dividend and Swing configurations must remain separate.

### 5.3 Strategy Evaluation

Strategy-specific interpretation of shared company intelligence.

Examples:

- Dividend evaluates income durability and long-term holding suitability.
- Swing evaluates momentum, entry timing, exit timing, and holding window.

### 5.4 Strategy Recommendation

Pre-decision strategy output submitted to the AI CIO.

A recommendation is not a final decision.

### 5.5 Strategy Lifecycle Record

Tracks installation, configuration, paper validation, operation, version update, suspension, and archival.

## 6. Portfolio Entities

### 6.1 Portfolio

The shared operational collection of paper holdings and cash reserves.

### 6.2 Position

Paper position in an asset with quantity, cost basis, current value, status, and dates.

Every Position must retain strategy attribution.

### 6.3 Holding Attribution

Breakdown of a shared asset holding by strategy.

Example:

- total AMD-related asset quantity: 125;
- Dividend attribution: 100;
- Swing attribution: 25.

### 6.4 Paper Order Intent

Non-executable representation of a proposed paper action.

It must never be accepted by a live broker adapter in Version 1.

### 6.5 Allocation Plan

Strategy-attributed target allocation with risk controls, reserve requirements, and effective date.

### 6.6 Portfolio Lifecycle Event

Append-only record of opening, adding, trimming, closing, re-entering, reserving, or archiving a paper position.

### 6.7 Cash Reserve

Unallocated paper capital, including reserve instruments such as SGOV when configured by the strategy or portfolio policy.

## 7. Reporting Entities

### 7.1 Report Definition

Shared template and rendering contract for a report type.

### 7.2 Report Instance

Generated report with explicit scope, period, strategy identifier, source records, metrics, warnings, decisions, and output paths.

### 7.3 Strategy Performance Period

Performance record for one strategy and one reporting period.

Dividend and Swing performance must never be merged into one strategy-performance record.

### 7.4 Delivery Record

Append-only record of report generation, storage, email delivery, retry, success, or failure.

## 8. Audit Entities

### 8.1 Audit Definition

Versioned audit contract describing required checks.

### 8.2 Audit Run

One execution of an audit against a platform, strategy, report, decision, release, or dataset.

### 8.3 Audit Finding

Individual pass, warning, or failure with evidence and remediation guidance.

### 8.4 Release Gate Result

Aggregate determination that permits or blocks packaging and deployment.

## 9. Learning Entities

### 9.1 Learning Record

Append-only lesson derived from outcomes, evidence quality, decisions, strategy performance, committee usefulness, or platform operation.

### 9.2 Outcome Observation

Measured result linked to a prior recommendation, decision, position, or report period.

### 9.3 Improvement Proposal

Suggested change to data sources, policies, thresholds, strategy logic, committees, constitution, or ecosystem.

An Improvement Proposal cannot silently change frozen behavior.

### 9.4 Ecosystem Comparison

Evaluation of whether another data source, service, model, or analytical ecosystem could reasonably have produced a better result.

## 10. Operational Entities

### 10.1 Scheduled Refresh

Read-only plan for recurring platform work. It does not create operating-system schedules by itself.

### 10.2 Platform Run

One paper-only execution cycle with start, end, status, inputs, outputs, warnings, and failures.

### 10.3 Health Snapshot

Point-in-time health state for services, required files, reports, configuration, and paper-only enforcement.

### 10.4 Diagnostic Finding

Operational issue or warning generated by diagnostics.

### 10.5 Version Registration

Record of module, strategy, blueprint, constitution, or platform version.

## 11. Ownership Rules

- Platform owns Company, Asset, MCIP, Evidence, shared intelligence, Portfolio, rendering infrastructure, auditing infrastructure, and learning infrastructure.
- AI CIO owns final automated Decision records.
- Committees own findings only.
- Strategies own evaluations, recommendations, configurations, reports, audits, performance histories, and learning attribution.
- Investor owns human override actions.
- No strategy may create a second company intelligence profile for the same company.
- No shared service may embed Dividend, Swing, Options, or future strategy behavior.

## 12. Version 1 Scope

Required for Version 1 implementation:

- shared platform entities;
- governance entities;
- portfolio entities;
- reporting and audit entities;
- learning entities;
- Dividend Strategy entities;
- paper-only operational entities.

Swing and Options entities may be represented by the shared contracts but are not required to be operational for the Dividend deployment release.

## 13. Change Control

This catalog is frozen for Version 1.0.0. New entities or material semantic changes require an Architecture Decision Record, catalog version increment, relationship review, data-dictionary update, and tests.

---

**Freeze declaration:** BP-002 Business Entity Catalog Version 1.0.0 is complete and frozen.