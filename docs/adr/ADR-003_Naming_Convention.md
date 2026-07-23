# ADR-003 Naming Convention

**Status:** ACCEPTED  
**Version:** 1.0.0

## Decision

The platform uses:

- `snake_case` for Python modules, functions, variables, JSON keys, database tables, and columns
- `PascalCase` for classes, dataclasses, and enums
- `UPPER_CASE` for constants
- singular business entity names
- descriptive filenames

## Rules

- Public names must be explicit and stable.
- Abbreviations are permitted only when established by the blueprint set, such as MCIP or AI CIO.
- Strategy outputs include the strategy name in scope metadata and storage paths.
- Report filenames use descriptive names and must not rely on ambiguous generic names when multiple strategies exist.

## Consequences

Legacy names may remain temporarily for compatibility, but new interfaces and migrations follow this convention.