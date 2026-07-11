# AI CIO Autonomous Mode

## Status

This document defines the autonomous paper-management architecture for the Trade-Dividend-Bot AI Chief Investment Officer layer.

The system remains paper-only:

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- no real order placement
- no Robinhood execution

## Purpose

The AI CIO may manage the paper portfolio without requiring daily approval, but only inside the approved Investment Policy Statement.

The investor defines the philosophy, objectives, limits, and override rights. The AI CIO may act freely only within those guardrails.

## Autonomy Levels

### Level 0 — Observer

- Reports conditions only
- Makes no recommendations
- Applies no paper changes

### Level 1 — Advisor

- Produces recommendations
- Requires `APPROVE`, `REJECT`, or `DEFER`
- Applies no paper change without approval

### Level 2 — Assisted CIO

May automatically apply low-risk paper actions such as:

- `KEEP`
- `WAIT`
- parking an affected allocation in SGOV during a mandatory earnings lock
- allocating new reserve cash within pre-approved limits

Major replacements and sector rotations require approval.

### Level 3 — Autonomous CIO

- Default long-term operating goal
- Manages the paper portfolio automatically inside the Investment Policy Statement
- Applies qualifying paper changes without prior approval
- Records every action in the Decision Journal
- Preserves investor veto, defer, and revert rights

### Level 4 — Live CIO

Reserved for a future architecture. It is not enabled by this project and must not be implemented without a separate safety design and explicit investor authorization.

## Default Mode

Until the investor explicitly changes it, the default is:

`LEVEL_1_ADVISOR`

The target paper operating mode is:

`LEVEL_3_AUTONOMOUS_CIO`

## Capital Actions

Supported actions are:

- `KEEP`
- `INCREASE`
- `REDUCE`
- `REPLACE`
- `WAIT`
- `PARK_IN_SGOV`
- `REENTER`
- `WATCH`

## Automatic Paper Actions

At Level 3, an action may be applied automatically only when all of the following are true:

1. The recommendation complies with the Investment Policy Statement.
2. Required evidence is present and sufficiently current.
3. The Capital Efficiency improvement exceeds the configured minimum when replacement is proposed.
4. The Decision Stability Score supports the change.
5. Concentration and correlation limits remain satisfied.
6. Earnings, lifecycle, drawdown, and sale gates are respected.
7. The action is fully explainable.
8. The before-and-after paper allocations can be journaled.

## Mandatory Protection Events

The system may automatically protect capital when a mandatory event occurs, including:

- earnings lock
- hard drawdown threshold
- severe risk breach
- broken investment thesis
- invalid or dangerously stale evidence
- strategy-specific forced exit condition

The default protective destination is SGOV unless the Investment Policy Statement specifies another reserve instrument.

A mandatory protection event does not automatically authorize a new replacement purchase. The affected allocation may remain in SGOV until a qualified replacement is approved or automatically authorized under the active autonomy level.

## Pair and Strategy Break Rules

Pairs and multi-asset strategies are temporary combinations, not permanent marriages.

If one member becomes disqualified:

1. Evaluate whether the unaffected member still qualifies independently.
2. Remove only the affected member when the remaining member continues to earn its place.
3. Park the affected allocation in SGOV while replacement candidates are evaluated.
4. Construct and score any replacement combination before applying it.
5. Replace the full strategy only when the complete strategy thesis has failed or a superior qualifying strategy exceeds the replacement threshold.

## Approval States

Recommendations use these states:

- `PROPOSED`
- `PENDING_APPROVAL`
- `APPROVED`
- `REJECTED`
- `DEFERRED`
- `AUTO_APPROVED_WITHIN_IPS`
- `APPLIED_TO_PAPER_PORTFOLIO`
- `OVERRIDDEN`
- `REVERT_REQUESTED`
- `REVERTED`
- `REVERT_BLOCKED_BY_SAFETY_RULE`

## Investor Controls

The investor must always be able to:

- approve
- reject
- defer
- veto an automatically applied paper action
- request a revert
- change the autonomy level
- disable autonomous paper changes

## Revert Rules

A revert creates a new decision record. It never deletes history.

Before restoring a previous paper holding, the system must confirm that the holding:

- is no longer under an earnings lock
- no longer has an active sale signal
- satisfies current risk limits
- remains eligible under current evidence

If direct restoration is unsafe, the affected allocation remains in SGOV while alternatives are reviewed.

## Decision Journal Requirement

Every automatically applied or investor-approved paper action must record:

- timestamp
- autonomy level
- portfolio before the change
- portfolio after the change
- full natural-language explanation
- Capital Efficiency Score, written in full
- Decision Stability Score, written in full
- confidence and evidence quality
- runner-up comparison
- Investment Policy rules authorizing the action
- investor approval, veto, defer, or revert information
- data freshness and missing-evidence warnings

## Governing Rule

The AI CIO may manage the paper portfolio autonomously only within the approved Investment Policy Statement, with complete transparency and permanent investor override rights.