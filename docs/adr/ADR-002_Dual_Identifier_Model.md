# ADR-002 Dual Identifier Model

**Status:** ACCEPTED  
**Version:** 1.0.0

## Decision

Every persistent business entity uses two identifiers:

- an internal UUID primary identifier
- a human-friendly external identifier

Examples include `DEC-2026-000001`, `EVR-2026-000183`, and `LRN-2026-000027`.

## Rationale

UUIDs provide durable internal identity across services and databases. Human-friendly identifiers improve reports, audits, troubleshooting, investor review, and operational communication.

## Rules

- UUIDs are immutable and never reused.
- External identifiers are unique within their entity type.
- External identifiers may include an entity prefix, year, and sequence.
- References in storage use UUIDs; reports may show both identifiers.
- Strategy and company symbols are not substitutes for entity identity.

## Consequences

Identifier generation becomes a shared platform service and requires concurrency-safe sequencing when PostgreSQL persistence is introduced.