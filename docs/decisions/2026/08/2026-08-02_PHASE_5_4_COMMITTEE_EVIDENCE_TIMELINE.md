# Phase 5.4 Committee Evidence Timeline

**Date:** 2026-08-02  
**Status:** Implemented; local validation pending

## Decision

Every strategy decision displays committee evidence as an ordered timeline. Each
step presents the committee or engine name, sequence, score, confidence, vote,
evidence status, and evidence rationale.

## Behavior

- Preserve the source committee order supplied by the strategy decision.
- Scope every timeline to its canonical decision ID.
- Render explicit empty evidence when no committee records exist.
- Retain the existing committee evidence table for backward compatibility.
- Escape all committee-supplied text.
- Apply the timeline in embedded portal workspaces and standalone previews.

## Strategy isolation

The timeline consumes only the committee evidence already contained in the
selected strategy's canonical Decision Journal. Phase 5.1 cross-strategy
rejection remains authoritative. The timeline does not merge evidence from
Dividend, Swing, or future strategies.

## Safety and compatibility

- Paper trading only
- Read-only and reporting-only
- No strategy execution or production-code imports
- No Robinhood or brokerage communication
- No orders or capital movement
- Canonical Decision Journal schema unchanged
- Enterprise KPI Contract v1.0 unchanged
