# ADR-006 Strategy Isolation

**Status:** ACCEPTED  
**Version:** 1.0.0

## Decision

Each strategy is an independent investment program operating on shared platform intelligence and infrastructure.

## Strategy-Owned Responsibilities

- strategy configuration and version
- interpretation of shared intelligence
- entry, exit, holding, allocation, and re-entry policy
- recommendations and strategy evaluations
- performance history
- reports and audits
- strategy-attributed learning

## Platform-Owned Responsibilities

- company identity and MCIP
- evidence
- shared intelligence calculations
- AI CIO constitutional governance
- consolidated paper portfolio
- reporting and audit renderers
- persistence, logging, diagnostics, and deployment infrastructure

## Rules

- Platform modules must not import strategy implementations.
- Strategies must not mutate another strategy's state, reports, policies, or learning.
- Every position and result must be attributable to a strategy.
- A strategy should operate as though it is the only strategy while respecting shared portfolio constraints.
- Strategy installation or removal must not require redesign of shared platform services.

## Consequences

The Dividend Strategy is the first Version 1 package. Swing and Options remain future packages that reuse the same shared intelligence without duplicating research.