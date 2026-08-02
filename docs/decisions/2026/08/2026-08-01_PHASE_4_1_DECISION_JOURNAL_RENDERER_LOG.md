# Phase 4.1 Decision Journal Renderer Decision Log

**Date:** 2026-08-01  
**Status:** Implemented; local validation pending  
**Scope:** Dividend and Swing strategy KPI workspaces

## Approved Decisions

1. The Decision Journal is strategy-scoped. A rendered KPI journal may contain only entries owned by the selected strategy ID.
2. Journal entries are ordered newest first.
3. Dividend entries render an ecosystem-pair identity consisting of the selected income ETF and leverage ETF. The UI also lists competing income and leverage alternatives and preserves the final pair-compatibility rationale.
4. Swing entries render an individual opportunity identity and preserve the Swing committee rank and Swing-only evidence.
5. Committee scores and evidence are expandable rather than crowding the initial scan view.
6. Supporting images are expandable and require path, caption, and image type metadata.
7. Empty journals render an explanatory safe-empty state.
8. All untrusted journal text is escaped before HTML publication.
9. The renderer and preview command are paper-only, read-only reporting components. They do not place orders, change allocations, or modify strategy calculations.

## Implementation

- `src/dividend_bot/strategy_decision_journal_renderer.py`
- `generate_strategy_decision_journal_preview.py`
- `tests/test_strategy_decision_journal_renderer.py`

## UI Placement

The renderer will populate the `Decision Journal` tab inside the selected strategy KPI workspace.

Approved KPI tabs:

- Executive Summary
- Portfolio
- Watchlist
- Income
- Alerts
- Decision Journal

Performance remains part of Executive Summary and deeper `More Details` analysis. Holdings remains part of Portfolio.

## Deployment Verification

- Dividend KPI never renders Swing decisions.
- Swing KPI never renders Dividend ecosystem decisions.
- The newest timestamp appears first.
- Dividend entries visibly identify both pair legs and the rejected alternatives.
- Images load from approved safe paths and include captions.
- Missing images or committee evidence produce explanatory empty states rather than fabricated content.
