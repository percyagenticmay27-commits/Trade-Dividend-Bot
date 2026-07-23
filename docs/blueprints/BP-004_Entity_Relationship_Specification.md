# BP-004 — Entity Relationship Specification

**Version:** 1.0.0  
**Status:** FROZEN

## 1. Purpose

This specification defines the canonical relationships among Platform Version 1 entities. It enforces one shared company-intelligence model, append-only governance history, strategy isolation, and separate strategy reporting and audits.

## 2. Core Relationship Model

```text
Company
  1 ─── 1 Master Company Intelligence Profile
  1 ─── * Asset
  1 ─── * Intelligence Snapshot
  1 ─── * Evidence Record
  1 ─── * Market Event
  1 ─── * Strategy Evaluation
  1 ─── * Learning Record

Master Company Intelligence Profile
  1 ─── * Intelligence Snapshot
  1 ─── * Strategy Evaluation
  1 ─── * Evidence Reference

Strategy Definition
  1 ─── * Strategy Configuration
  1 ─── * Strategy Evaluation
  1 ─── * Strategy Recommendation
  1 ─── * AI CIO Decision
  1 ─── * Position
  1 ─── * Report Instance
  1 ─── * Audit Run
  1 ─── * Learning Record

AI CIO Decision
  * ─── 1 Strategy Definition
  * ─── 1 Asset
  * ─── 0..1 Company
  * ─── 0..1 Strategy Evaluation
  1 ─── * Evidence Reference
  1 ─── * Committee Finding Reference
  1 ─── 0..1 Investor Override
  0..1 ─── 0..1 Superseded Decision

Portfolio
  1 ─── * Position
  1 ─── * Allocation Plan
  1 ─── * Portfolio Lifecycle Event
  1 ─── * Cash Reserve

Position
  * ─── 1 Portfolio
  * ─── 1 Strategy Definition
  * ─── 1 Asset
  1 ─── * Portfolio Lifecycle Event
```

## 3. Company and MCIP

### 3.1 One Company, One Logical MCIP

Each Company must have exactly one current logical Master Company Intelligence Profile.

Historical state is represented by Intelligence Snapshots, not by creating competing strategy-owned profiles.

Prohibited relationships:

- Dividend-owned MCIP;
- Swing-owned MCIP;
- Options-owned MCIP;
- duplicate profiles for the same company and effective period without an explicit supersession relationship.

### 3.2 Company to Asset

A Company may have multiple Assets, including common equity, preferred equity, or related listed instruments.

An Asset may reference an underlying Asset when it is leveraged, derivative, or benchmark-linked.

### 3.3 Company Lifecycle

The supported company lifecycle is:

```text
DISCOVERED
→ RESEARCHING
→ INTELLIGENCE_BUILT
→ RANKED
→ WATCHLISTED
→ CANDIDATE
→ OWNED
→ EXITED
→ ARCHIVED
```

Lifecycle events must be historical records; current status may be derived from the latest valid event.

## 4. Evidence Relationships

### 4.1 Evidence Subject

An Evidence Record must relate to at least one supported subject:

- Company;
- Asset;
- AI CIO Decision;
- Policy;
- Constitution Version;
- Platform Run;
- Market Event.

### 4.2 Append-Only Timeline

Each Evidence Record may have zero or more Evidence Append Entries.

```text
Evidence Record
  1 ─── * Evidence Append Entry
```

Append entries may extend, correct, clarify, or resolve evidence. They may not replace the parent record or delete prior entries.

### 4.3 Decision Evidence

A Decision may reference many Evidence Records, and one Evidence Record may support many Decisions.

This is a many-to-many relationship implemented through an immutable Decision Evidence Reference entity or equivalent join structure.

## 5. Strategy Relationships

### 5.1 Shared Intelligence, Separate Interpretation

Each Strategy Evaluation references:

- exactly one Strategy Definition;
- exactly one Company;
- exactly one current or historical MCIP source;
- zero or one specific Asset;
- the Strategy Configuration version applied.

Multiple strategies may evaluate the same MCIP independently.

### 5.2 Evaluation to Recommendation

A Strategy Evaluation may produce zero or more Strategy Recommendations.

A Recommendation must retain the originating Evaluation and Strategy identifiers.

A Recommendation is advisory and cannot directly create or modify a Position.

### 5.3 Recommendation to AI CIO Decision

The AI CIO may consume one or more recommendations, but every final Decision is strategy-scoped.

A Decision must not combine Dividend and Swing recommendations into one final strategy decision.

## 6. Committee Relationships

```text
Committee
  1 ─── * Committee Finding

AI CIO Decision
  * ─── * Committee Finding
```

Committee Findings are immutable outputs linked to their Committee, subject, evidence references, and analysis time.

Committees do not own Decisions and cannot transition Decision state directly except through a validated request for AI CIO review.

## 7. Investor Override Relationships

An Investor Override must reference exactly one original AI CIO Decision and exactly one Investor.

```text
Investor
  1 ─── * Investor Override

AI CIO Decision
  1 ─── 0..1 Investor Override
```

For Version 1, a Decision may have at most one effective override. Further changes must create a superseding Decision or a new governed override record, never mutate the prior override.

The original Decision remains preserved.

## 8. Decision History and Supersession

Decisions form a directed historical chain.

```text
Decision A
  └── superseded_by → Decision B
       └── superseded_by → Decision C
```

Rules:

- a Decision may supersede at most one prior Decision;
- a Decision may be superseded by at most one active successor within the same strategy and subject scope;
- cycles are prohibited;
- all prior decisions remain queryable;
- strategy, company, and asset scope must remain compatible across the chain.

## 9. Portfolio Relationships

### 9.1 One Shared Portfolio, Strategy Attribution

The platform may operate one shared paper Portfolio while preserving separate strategy ownership of Positions.

The same Asset may appear in multiple Positions when each Position has a different Strategy attribution.

Example:

```text
Portfolio
  ├── Position: AMDL / Dividend / 100 shares
  └── Position: AMDL / Swing / 25 shares
```

Operational portfolio views may aggregate to 125 shares, but strategy reports must use the attributed quantities and returns.

### 9.2 Decision to Position

An implemented paper Decision may create or update a Position through a Portfolio Lifecycle Event.

Recommended relationship:

```text
AI CIO Decision
  1 ─── 0..* Portfolio Lifecycle Event

Position
  1 ─── * Portfolio Lifecycle Event
```

No Decision directly executes a broker order in Version 1.

### 9.3 Allocation

Each Allocation Plan belongs to one Portfolio and one Strategy for its strategy-specific targets.

A platform-level allocation summary may aggregate plans but must retain source Strategy identifiers.

## 10. Reporting Relationships

### 10.1 Shared Definition, Isolated Instance

A Report Definition may be reused by many strategies.

A strategy Report Instance must reference exactly one Strategy.

```text
Report Definition
  1 ─── * Report Instance

Strategy Definition
  1 ─── * Report Instance
```

Platform reports use a null Strategy relationship and an explicit platform scope.

### 10.2 Report Source Manifest

Each Report Instance must preserve references to the data, decisions, positions, and versions used to create it.

Weekly and monthly reports for Dividend, Swing, Options, and future strategies are separate Report Instances even when they share a template.

### 10.3 Delivery

A Report Instance may have many Delivery Records due to multiple destinations, retries, or delivery attempts.

## 11. Audit Relationships

An Audit Run has exactly one Audit Definition and one explicit scope.

Scopes include:

- Platform;
- Strategy;
- Decision;
- Evidence;
- Report;
- Release;
- Deployment.

A strategy Audit Run must reference exactly one Strategy. Dividend and Swing audit findings must not be merged into one strategy audit result.

An Audit Run has one or more Audit Findings.

## 12. Learning Relationships

A Learning Record may reference one or more of:

- Company;
- Asset;
- Strategy;
- Evaluation;
- Decision;
- Position;
- Evidence Record;
- Committee Finding;
- Audit Finding;
- Report Instance;
- Platform Run.

Learning records are append-only and attribution must be preserved.

Platform learning may compare lessons across strategies, but it must not rewrite or merge their historical performance records.

## 13. Operational Relationships

```text
Platform Run
  1 ─── * Generated Report
  1 ─── * Audit Run
  1 ─── * Diagnostic Finding
  1 ─── * Health Snapshot
  1 ─── * Evidence Append Entry
```

A Scheduled Refresh may trigger many Platform Runs over time. The scheduling definition remains separate from execution history.

## 14. Referential Integrity Rules

1. Deleting a Company with dependent history is prohibited; archive instead.
2. Deleting Evidence, Decisions, Overrides, Audit Runs, Learning Records, and Portfolio Lifecycle Events is prohibited in normal operation.
3. Deleting a Strategy Definition with dependent records is prohibited; archive it.
4. Strategy-scoped child records must use the same Strategy identity as their parent chain.
5. A Report Instance cannot reference source records from another strategy unless it is explicitly a platform-level comparative report; such a report must preserve all strategy attribution and cannot replace the separate strategy reports.
6. A Position must always identify the Strategy responsible for it.
7. An MCIP must remain strategy-neutral.

## 15. PostgreSQL Mapping Guidance

Recommended relational implementation:

- UUID primary keys;
- unique indexes on external identifiers;
- unique constraint on current logical MCIP per Company;
- foreign keys for all defined ownership relationships;
- join tables for Decision–Evidence and Decision–Committee Finding relationships;
- immutable-history enforcement through application contracts and restricted database permissions;
- JSONB only for extensible metadata, warnings, manifests, and structured findings—not as a substitute for core relationships.

## 16. Version 1 Compatibility

Existing JSON and CSV files may remain operational adapters while the platform foundation is introduced. Adapters must map records to the canonical entities and relationships defined here without changing existing paper-only behavior.

## 17. Change Control

Relationship cardinality changes, ownership changes, deletion-policy changes, or strategy-isolation changes require an ADR, BP-002 and BP-003 updates, migration analysis, compatibility tests, and release-audit approval.

---

**Freeze declaration:** BP-004 Entity Relationship Specification Version 1.0.0 is complete and frozen.