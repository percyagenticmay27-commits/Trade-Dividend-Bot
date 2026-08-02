# Phase 5.3 Decision Journal Image Gallery

**Date:** 2026-08-02  
**Status:** Implemented; local validation pending

## Decision

Strategy-owned evidence images are displayed inside the selected strategy's
Decisions tab as a responsive gallery. Each thumbnail carries its decision ID,
image order, image type, and escaped caption. Selecting a thumbnail opens the full-size image in a separate read-only browser tab.

## Behavior

- Preserve source image ordering within each decision.
- Lazy-load thumbnails.
- Display image type and caption.
- Provide a script-free full-size image link with safe new-tab isolation.
- Render a clear empty state when no images exist.
- Render an unavailable card for unsafe image paths.
- Support the same gallery in embedded portal views and standalone previews.\n- Preserve the existing rule that rendered journal fragments contain no scripts.

## Security and isolation

- Reject `javascript:`, `vbscript:`, and HTML data-document image paths.
- Escape paths, captions, types, and decision identifiers.
- Images remain owned by the journal's strategy and decision.
- Phase 5.1 cross-strategy journal rejection remains authoritative.
- No file writes, strategy imports, broker calls, orders, or capital movement.

## Compatibility

The canonical Decision Journal schema and Enterprise KPI Contract v1.0 remain
unchanged. Existing journals without images retain the established safe empty
state.
