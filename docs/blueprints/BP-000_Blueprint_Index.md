# BP-000 — Blueprint Index

**Version:** 1.0.0  
**Status:** FROZEN  
**Platform release:** Version 1 Foundation  
**Primary delivery target:** Dividend Strategy paper-trading deployment

## Purpose

This index defines the authoritative blueprint set for evolving Trade-Dividend-Bot into a strategy-neutral investment platform while preserving the existing Dividend Bot as the first production strategy package.

## Governing Blueprint Set

| ID | Document | Purpose | Status |
|---|---|---|---|
| BP-000 | Blueprint Index | Defines the blueprint system and traceability | FROZEN |
| BP-001 | AI CIO Constitution | Defines authority, governance, decision states, and investor override | AUTHORING |
| BP-002 | Business Entity Catalog | Defines platform, intelligence, evidence, decision, portfolio, strategy, report, audit, and learning entities | AUTHORING |
| BP-003 | Enterprise Data Dictionary | Defines canonical field names, types, constraints, identifiers, and ownership | AUTHORING |
| BP-004 | Entity Relationship Specification | Defines entity relationships and strategy-scoping rules | AUTHORING |
| BP-005 | Platform Service Catalog | Defines shared platform services and strategy boundaries | AUTHORING |
| BP-006 | Module Contract Library | Defines public module contracts, inputs, outputs, errors, and invariants | AUTHORING |
| BP-007 | Dependency-Aware Build Sequence | Defines the mandatory implementation and validation order | AUTHORING |
| BP-008 | Implementation Blueprint | Defines repository, coding, testing, migration, reporting, and deployment standards | AUTHORING |

## Frozen Architecture Decisions

The blueprint set incorporates these approved decisions:

1. PostgreSQL is the target production database; Version 1 may continue using existing files while persistence contracts are introduced.
2. Internal identifiers use UUIDs; external records may use human-friendly identifiers.
3. Code and data naming use `snake_case`; Python classes use `PascalCase`.
4. Each company has one shared Master Company Intelligence Profile.
5. Strategy reports are isolated. Dividend, Swing, Options, and future strategy returns and decisions are reported separately.
6. Every strategy is an independent investment program operating on shared platform intelligence and infrastructure.
7. Evidence is append-only. Corrections and follow-ups create new entries rather than overwriting history.
8. The AI CIO alone issues the final automated investment decision. Committees analyze, score, recommend, question, and collaborate only.
9. The investor may override an AI CIO decision only with a reason, audit trail, preserved original decision, and linked history.
10. Version 1 remains paper-only and cannot place real broker orders.

## Strategy Reporting Rule

The reporting framework is shared, but report content is strategy-specific.

Required separation includes:

- Dividend daily, weekly, monthly, performance, learning, and audit reports
- Swing daily, weekly, monthly, trade, performance, learning, and audit reports
- Future strategy reports using the same rendering contracts but independent data and decisions
- Platform reports for health, evidence integrity, AI CIO governance, data quality, deployment, and operations

A platform-level holdings view may aggregate shares operationally, but it must preserve strategy attribution and must not replace separate strategy return reporting.

## Implementation Priority

```text
1. Repository hygiene and classification
2. Blueprint and ADR freeze
3. Platform foundation contracts
4. Shared business entities and identifiers
5. Master Company Intelligence Profile
6. Evidence and AI CIO governance
7. Portfolio strategy attribution
8. Strategy registry and lifecycle
9. Dividend Strategy isolation and adapters
10. Strategy-specific reporting and auditing
11. End-to-end paper-cycle validation
12. Cloud deployment validation
13. Platform Version 1 and Dividend Strategy Version 1 freeze
```

## Change Control

After a blueprint is marked `FROZEN`, modifications require:

- A documented reason
- Impact analysis
- A new or amended Architecture Decision Record
- Updated tests or validation requirements where applicable
- Confirmation that strategy isolation and paper-only operation remain intact

## Source of Truth

The GitHub branch `platform-v1-foundation` is the controlled implementation branch. The `main` branch remains the deployment baseline until the foundation passes its release gates and is approved for merge.

## Freeze Statement

BP-000 Version 1.0.0 is frozen. It may be amended only through the approved change-control process.
