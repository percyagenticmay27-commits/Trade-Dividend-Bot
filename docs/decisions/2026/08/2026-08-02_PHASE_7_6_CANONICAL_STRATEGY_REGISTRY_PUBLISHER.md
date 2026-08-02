# Phase 7.6 — Canonical Enterprise Strategy Registry Publisher

## Decision

A tracked, reviewable registry source now publishes the canonical
`DIVIDEND-001` and `SWING-001` registrations after generated runtime results
are absent or stale. This closes the operational reconstruction gap discovered
during the Phase 7.5 local handoff.

The publisher replaces canonical entries from the tracked source and preserves
unrelated external strategy registrations. It does not create KPI values,
allocations, decisions, positions, or strategy evidence.

## Safety

Every canonical plugin must be paper-compatible, advisory-only, reporting-only,
and explicitly disable live trading, broker execution, capital movement,
automatic activation, and direct database writes. Unsafe source entries block
publication without changing the runtime registry.

## Files

- `config/enterprise_strategy_registry.json`
- `src/dividend_bot/enterprise_strategy_registry_publisher.py`
- `publish_enterprise_strategy_registry.py`
- `results/enterprise_dividend_service_registry.json` (generated)
