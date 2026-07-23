# ADR-004 Master Company Intelligence Profile

**Status:** ACCEPTED  
**Version:** 1.0.0

## Decision

The platform maintains exactly one Master Company Intelligence Profile (MCIP) per company.

## Scope

MCIP contains shared company identity, discovery, fundamentals, growth, income facts, financial health, risk, technical calculations, market intelligence, themes, earnings, watchlist intelligence, evidence links, and learning links.

MCIP does not contain strategy recommendations, entries, exits, allocations, or investment decisions.

## Rationale

Dividend, Swing, Options, and future strategies must consume one shared factual foundation rather than duplicate research or maintain conflicting company records.

## Consequences

- Shared intelligence services update MCIP.
- Strategies interpret MCIP independently.
- Corrections preserve lineage and evidence history.
- Historical snapshots may be retained without creating multiple canonical profiles.
- Strategy code must not mutate shared facts.