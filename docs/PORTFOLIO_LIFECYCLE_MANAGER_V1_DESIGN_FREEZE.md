# Portfolio Lifecycle Manager Version 1.0 Design Freeze

## Status

- Version: 1.0
- Lifecycle: DESIGN FROZEN
- Implementation status: Approved for development
- Operating mode: Paper-only

## Purpose

The Portfolio Lifecycle Manager is the authoritative source of the current state and complete life story of every portfolio allocation.

The Decision Journal records what happened and why. The Portfolio Lifecycle Manager maintains what is true now.

## Permanent Architecture Distinction

### Decision Journal

The Decision Journal is an immutable, chronological record of decisions and events.

It answers:

> What did the AI CIO decide on a given date, and why?

### Portfolio Lifecycle Manager

The Portfolio Lifecycle Manager maintains current allocation-centered state.

It answers:

> What is the current status of this allocation, why is it in that state, and what happens next?

The Lifecycle Manager may consume Decision Journal events, but it must not replace or rewrite the journal.

## Responsibilities

The module shall:

- maintain every active, protected, pending, replaced, and closed allocation,
- identify where portfolio capital is currently deployed,
- track allocation rank and percentage,
- track open date and days held,
- track the original and current investment thesis,
- track the latest Capital Efficiency Score,
- track the latest Decision Stability Score,
- track Evidence Confidence,
- track market regime and sector context,
- track the strongest challenger,
- track replacement eligibility,
- track earnings locks, sale signals, risk breaches, and data-protection events,
- track SGOV parking and release conditions,
- track re-entry eligibility,
- track next review date or trigger,
- link each allocation to its latest Decision Journal entry,
- expose current state to dashboards, timelines, replacement managers, reports, and future orchestration modules.

## Permanent Investment Philosophy

The Lifecycle Manager shall remain opportunity-driven and sector-neutral.

Sector information is context only. It shall never create a guaranteed allocation, sector quota, or entitlement to capital.

## Lifecycle States

Version 1.0 shall support:

- `CANDIDATE`
- `ACTIVE`
- `MONITORING`
- `PARKED_IN_SGOV`
- `REENTRY_PENDING`
- `REPLACEMENT_PENDING`
- `REPLACED`
- `CLOSED`

## Lifecycle State Meaning

### CANDIDATE

A qualified opportunity under evaluation that does not currently hold portfolio capital.

### ACTIVE

An allocation currently holds paper-portfolio capital and remains qualified.

### MONITORING

The allocation remains active but has weakening evidence, a narrowing advantage, an approaching event, or another condition requiring increased review.

### PARKED_IN_SGOV

The affected capital has been temporarily moved to SGOV because of an earnings lock, mandatory protection rule, invalid critical data, or another approved safety condition.

### REENTRY_PENDING

The original or another candidate may receive capital after protection clears, but entry, risk, evidence, and opportunity-ranking requirements have not yet all passed.

### REPLACEMENT_PENDING

The current allocation no longer qualifies for an unrestricted hold, but a final replacement has not yet passed all gates.

### REPLACED

The allocation was superseded by another qualified opportunity. The replacement relationship and reason must be preserved.

### CLOSED

The allocation no longer holds capital and has no pending re-entry or replacement workflow.

## Required Allocation Record

Each allocation record shall contain, where available:

### Identity

- allocation ID,
- strategy or instrument name,
- component symbols,
- strategy type,
- sector context,
- current rank.

### Capital State

- lifecycle state,
- current allocation percentage,
- current paper value,
- SGOV-linked percentage or value,
- portfolio before and after the latest change.

### Dates and Maturity

- opened date,
- last updated date,
- last reviewed date,
- days held,
- allocation maturity state,
- next review date or trigger.

### Evaluation

- Capital Efficiency Score,
- Decision Stability Score and label,
- Evidence Confidence and label,
- market regime,
- current recommendation,
- natural explanation,
- strongest challenger,
- challenger score difference,
- replacement eligibility.

### Protection

- earnings-lock status,
- confirmed sale-signal status,
- risk-breach status,
- invalid-data protection status,
- SGOV reason,
- SGOV release condition,
- re-entry eligibility.

### History Links

- latest Decision Journal entry ID,
- prior allocation ID when replaced,
- replacement allocation ID,
- number of SGOV parking events,
- number of replacements,
- number of reviews.

## Allocation Maturity

Version 1.0 shall classify allocation maturity as:

- `NEW`
- `DEVELOPING`
- `ESTABLISHED`
- `LONG_TERM_LEADER`

Maturity reflects time and demonstrated persistence. Age alone must never block a clearly justified protection or replacement decision.

Suggested default interpretation:

- NEW: 0–5 calendar days,
- DEVELOPING: 6–20 calendar days,
- ESTABLISHED: 21–89 calendar days,
- LONG_TERM_LEADER: 90 or more calendar days.

These thresholds may be configurable, but the public maturity labels are frozen for Version 1.0.

## Event Processing Rules

The manager shall consume approved lifecycle events such as:

- allocation opened,
- allocation reviewed,
- allocation increased,
- allocation reduced,
- earnings lock started,
- capital parked in SGOV,
- protection cleared,
- re-entry approved,
- replacement prepared,
- replacement applied,
- allocation closed,
- investor override recorded,
- revert request evaluated.

Events update current state but do not erase previous state or journal history.

## SGOV Rules

For every SGOV-linked allocation, the manager must store:

- source allocation,
- amount or percentage moved,
- reason,
- whether the move was automatic or investor-approved,
- current status,
- release condition,
- expected or next review,
- candidate competing for the released capital.

Capital shall not automatically return to the prior investment. All candidates must compete again under current evidence.

## Public Functions

The implementation shall provide public functions equivalent to:

- `build_portfolio_lifecycle(...)`
- `apply_lifecycle_event(...)`
- `apply_decision_journal_entry(...)`
- `get_allocation_state(...)`
- `list_active_allocations(...)`
- `list_sgov_allocations(...)`
- `list_pending_allocations(...)`
- `format_portfolio_lifecycle_markdown(...)`
- `write_portfolio_lifecycle(...)`
- `build_and_write_portfolio_lifecycle(...)`

Exact function signatures may be finalized during implementation, but public names and responsibilities should follow this pattern.

## Required Outputs

- `portfolio_lifecycle.json`
- `portfolio_lifecycle.md`
- `portfolio_lifecycle.html`

HTML output may remain functionally simple until the approved final HTML/UI modernization phase.

## JSON Requirements

The JSON output shall include:

- module metadata,
- paper-only safety flags,
- generated timestamp,
- portfolio summary counts,
- active allocation records,
- SGOV allocation records,
- pending records,
- closed or replaced records,
- warnings,
- errors.

## Markdown Layout

The Markdown report shall show:

1. Portfolio Lifecycle Summary
2. Active Allocations
3. SGOV and Protection Activity
4. Re-entry and Replacement Pending
5. Recently Replaced or Closed Allocations
6. Next Reviews
7. Paper-Only Safety

Investor-facing text must use full metric names and natural explanations.

## Testing Plan

Unit tests shall cover:

- public functions exist,
- paper-only flags,
- creation of active allocation state,
- state transitions,
- invalid state-transition rejection,
- Decision Journal event application,
- SGOV parking and release-condition tracking,
- re-entry pending behavior,
- replacement relationship tracking,
- allocation maturity classification,
- rank and allocation updates,
- preservation of prior history,
- query functions,
- JSON, Markdown, and HTML output creation,
- empty portfolio handling,
- malformed input handling,
- finite-number validation,
- prohibited broker or order-execution calls.

## Integration Order

The approved flow is:

```text
AI CIO Decision Engine
        ↓
Decision Journal Engine
        ↓
Portfolio Lifecycle Manager
        ↓
Executive Dashboard
Portfolio Timeline
Opportunity Replacement Manager
Weekly Board Report
Annual Letter
```

## Deferred Final HTML/UI Modernization

The final visual modernization remains an approved roadmap phase but is not part of the Version 1.0 Lifecycle Manager implementation.

The project will complete core logic, orchestration, data flow, reports, and tests before applying the shared final HTML renderer and user-interface design system.

## Freeze Rule

The Version 1.0 implementation may add internal helpers and validation, but it must preserve the responsibilities, lifecycle states, opportunity-driven philosophy, paper-only rules, and Decision Journal distinction defined here.
