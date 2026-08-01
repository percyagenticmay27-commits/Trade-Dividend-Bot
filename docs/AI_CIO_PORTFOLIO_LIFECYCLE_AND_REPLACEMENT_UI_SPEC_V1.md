# AI CIO Portfolio Lifecycle and Replacement UI Specification v1.0

## Purpose

This document preserves the recovered portfolio-lifecycle, replacement, and report-display decisions that govern the Enterprise AI CIO and any current or future registered strategy.

Use it during development, testing, final HTML modernization, and DigitalOcean deployment verification. A missing or contradictory deployed behavior is a defect unless a later dated decision explicitly supersedes this specification.

## Governing Portfolio Constitution

All lifecycle and replacement behavior must remain aligned with the AI CIO Portfolio Constitution:

- Maximize long-term Total Wealth: Growth plus Income.
- Paper-only operation; no live brokerage execution.
- Allocate by qualified opportunity, not predetermined sector or asset-class quotas.
- No stock, ETF, pair, sector, growth, or dividend bias.
- Evidence first.
- Protection before performance.
- Decision stability and resistance to unnecessary turnover.
- Explainability.
- Auditability.
- Human oversight and inspectability.

## Authoritative Lifecycle State

The Portfolio Lifecycle Manager is the authoritative current-state source for each allocation. Dashboard consumers must query the current lifecycle artifact rather than replaying the complete event history.

Normalized lifecycle states include:

- Candidate
- Active
- Monitoring
- Protected / SGOV-protected
- Reenter Pending
- Replacement Pending
- Replaced
- Closed

Each allocation should expose, when supplied by the owning strategy:

- strategy ID and name
- symbol, pair, contract, or instrument ID
- allocation rank
- dollar amount first, percentage second
- paper value
- days held
- maturity: New, Developing, Established, Long-Term Leader
- CES or equivalent capital-efficiency score
- Decision Stability score
- evidence confidence
- market regime
- challenger
- latest Decision Journal entry
- SGOV reason
- SGOV release condition
- authorization and re-entry status
- replacement relationship
- preserved event history

## Default Continuation Rule

A routine review does not require the investor to authorize continuation.

When no user action is taken:

> The current allocation continues under the existing paper-only lifecycle and protection rules.

The UI must not label default continuation as `Must authorize change`.

User actions should represent exceptions or explicit oversight choices, such as:

- Override
- Revert
- Defer
- Inspect

The exact gate and threshold combination that may permit a future automatic paper-mode replacement transition is not frozen by the recovered discussion. It must be documented in a later dated decision before implementation.

Until that freeze, the UI must clearly distinguish:

- Continue current allocation
- Review recommended
- Replacement pending
- User override
- User revert
- Deferred decision
- Future explicitly authorized automatic transition

## Replacement Gate Display

Every Replacement Gate and material lifecycle label requires a concise explanation or help link.

The help content must state:

- what the label means
- how it is calculated
- why it matters
- whether it is a hard gate, warning, or context-only signal
- the evidence supporting it
- whether investor action is required

This applies to:

- Decision Stability
- current-versus-challenger comparison
- meaningful-improvement threshold
- protection gates
- SGOV release conditions
- replacement readiness
- evidence-confidence gates
- risk vetoes
- strategy-specific replacement gates

## Compare Current and Challenger

The comparison view must show the current allocation and challenger side by side using recorded evidence only.

Recommended fields include:

- allocation value
- allocation percentage
- rank
- CES or capital efficiency
- Opportunity Quality or equivalent quality score
- Decision Stability
- evidence confidence
- regime alignment
- risk and protection status
- lifecycle maturity
- expected improvement
- replacement gates passed or failed
- Decision Journal links

The decision-language column must explain the actual state. It must not imply required manual authorization merely because a review occurred.

## Approved Page Layout

Preserve the original page structure rather than converting the principal report sections into overlapping tabs.

Required layout:

1. Left navigation.
2. Horizontal executive summary cards at the top.
3. Dollar amount before percentage for monetary allocation displays.
4. A `More` or `Details` link on each relevant summary card.
5. One shared analysis workspace below the cards.
6. Detailed contributor, lifecycle, or challenger table inside that workspace.
7. Metric definitions and help links.
8. AI CIO commentary based on recorded evidence.

The selected `More/Details` action updates the shared analysis workspace. Cards should not each expand independently, and a separate browser page is not required for every metric.

## Shared Strategy Contract

This lifecycle and replacement UI is strategy-agnostic. Dividend, Swing, Options, Futures, and future plugins must publish their lifecycle and decision evidence through Registry v2 artifact roles rather than requiring strategy-specific host imports.

Expected artifact roles include:

- current lifecycle state
- Decision Journal
- challenger and replacement comparison
- protection / SGOV state
- allocation and ranking
- scores and confidence
- committee evidence
- event history

## Paper-Only Safety

This specification changes reporting and explainability only. It does not authorize:

- live trading
- broker execution
- real capital movement
- hidden automatic allocation changes
- bypassing protection rules
- inventing missing evidence

## Acceptance Criteria

The implementation is complete only when:

1. Current lifecycle state is visible for each allocation.
2. Dollar amount appears before percentage.
3. Allocation maturity is shown when reported.
4. SGOV reason and release condition are shown when applicable.
5. Current-versus-challenger comparison is available.
6. Every replacement gate has explanatory help.
7. No action defaults to continuing the current allocation.
8. The UI distinguishes continuation, review, pending replacement, override, revert, and defer.
9. The original horizontal-card layout and shared analysis workspace are preserved.
10. Decision Journal and supporting evidence links are available when declared.
11. Missing evidence is labeled rather than invented.
12. No component enables live execution or real capital movement.

## DigitalOcean Deployment Verification

After deployment, verify:

- Lifecycle states match the authoritative lifecycle artifact.
- No current allocation incorrectly requires repetitive manual approval to continue.
- `More/Details` opens the shared analysis workspace.
- Dollar values precede percentages.
- Replacement Gate labels have working definitions or help links.
- Current and challenger evidence is visible and traceable.
- SGOV protection and re-entry information appears when applicable.
- Missing lifecycle or replacement sections are treated as deployment defects against this document.

## Related Daily Decisions

- `DEC-2026-08-01-008`
- `DEC-2026-08-01-009`
- `DEC-2026-08-01-010`
- `DEC-2026-08-01-011`
- `DEC-2026-08-01-012`

See:

- `docs/decisions/2026/08/2026-08-01_DECISION_LOG.md`
- `docs/ENTERPRISE_INVESTOR_DASHBOARD_UI_SPEC_V1.md`
