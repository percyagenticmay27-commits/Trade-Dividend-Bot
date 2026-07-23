# BP-006 Module Contract Library

**Version:** 1.0.0  
**Status:** FROZEN

## Purpose

Define mandatory implementation contracts for all platform, strategy, reporting, audit, learning, and deployment modules.

## Global Module Contract

Every production module must expose or document:

- `MODULE_NAME`
- `MODULE_VERSION`
- `MODULE_DESCRIPTION`
- explicit public dataclasses and functions
- typed inputs and outputs
- validation behavior
- warnings and errors
- deterministic serialization where applicable
- paper-only enforcement where investment behavior is involved

Public interfaces must not change without a version update and migration note.

## Foundation Contract

Foundation modules may provide configuration, identifiers, serialization, logging, registries, validation, and paths. They must contain no company selection, investment scoring, entry, exit, or allocation logic.

## MCIP Contract

The Master Company Intelligence Profile module must:

- maintain one canonical profile per company
- store shared facts and calculated intelligence
- preserve source and observation timestamps
- exclude strategy recommendations and decisions
- support serialization suitable for PostgreSQL migration
- treat missing evidence according to the owning component's published rule

## Evidence Contract

Evidence modules must:

- create immutable evidence records
- append corrections and follow-ups rather than overwrite
- preserve source, observed time, effective time, confidence, and subject links
- expose chronological retrieval
- reject deletion through normal application services

## AI CIO Contract

AI CIO modules must:

- consume evidence, MCIP, policy, constitution, committee analysis, and learning
- create exactly one automated decision for a strategy evaluation
- preserve decision reasoning, confidence, risks, evidence links, and state
- prohibit committee voting or score averaging as decision authority
- support investor override without changing the original decision

## Strategy Contract

Each strategy package must expose equivalent lifecycle operations:

- `initialize`
- `validate_configuration`
- `evaluate_company`
- `evaluate_positions`
- `build_recommendations`
- `build_report_models`
- `build_audit_models`
- `record_learning`

Each output must include `strategy_id` and `strategy_version`. A strategy may interpret shared intelligence but must not mutate MCIP facts.

## Portfolio Contract

Portfolio modules must:

- remain paper-only
- preserve consolidated holdings
- attribute every lot and result to a strategy
- calculate realized and unrealized results deterministically
- prevent strategy reports from claiming returns belonging to another strategy

## Reporting Contract

Reporting modules must:

- accept one explicit strategy scope or the platform scope
- render common templates to JSON, CSV, and Markdown
- keep Dividend, Swing, Options, and future reports separate
- support daily, weekly, monthly, performance, learning, and audit report types
- reject mixed-strategy report payloads unless the output is explicitly a platform-level aggregation that preserves per-strategy sections

## Audit Contract

Audit modules must identify scope, period, version, checks, findings, severity, evidence, and remediation. Strategy audits must remain isolated. Platform audits must not determine strategy investment performance.

## Learning Contract

Learning modules must preserve the source scope, including strategy attribution. A Dividend lesson cannot silently modify Swing policy. Proposed policy changes require validation and approval before adoption.

## Error Contract

- Required missing input: explicit error.
- Optional missing input: warning and documented fallback.
- Malformed input: validation error; never silently accepted.
- Non-finite numeric values: rejected or normalized only under a published contract.
- Live-trading request: rejected.

## Test Contract

Every new module requires:

- syntax compilation
- unit tests for public behavior
- boundary and malformed-input tests
- paper-only tests where applicable
- deterministic output tests
- strategy-isolation tests where applicable

## Freeze Statement

These contracts are frozen for Platform Version 1.0. Exceptions require an ADR.