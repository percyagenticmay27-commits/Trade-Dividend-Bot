# ADR-001 PostgreSQL Primary Persistence

**Status:** ACCEPTED  
**Version:** 1.0.0

## Decision

PostgreSQL is the target primary relational database for the Investment Intelligence Platform.

## Context

The platform requires durable relationships, transactional integrity, append-only evidence, strategy attribution, auditability, and future cloud operation. Existing JSON, CSV, and Markdown outputs remain valid reporting and interchange formats during migration.

## Consequences

- Canonical entities must map cleanly to PostgreSQL tables.
- UUIDs are primary keys.
- Foreign keys preserve company, strategy, evidence, decision, portfolio, and audit relationships.
- JSONB may be used for flexible derived payloads, but core identity and relationship fields remain relational.
- Database introduction must not break current file-based paper workflows.
- Migrations must be versioned and reversible.

## Rejected Alternatives

SQLite as the permanent primary store was rejected because the intended cloud platform requires stronger concurrent, relational, and operational capabilities. File-only persistence remains transitional, not the target architecture.