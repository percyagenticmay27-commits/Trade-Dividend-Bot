# AI CIO Dashboard Version 2.0 Freeze

## Status

- Version: 2.0
- Lifecycle: FROZEN
- Approval Status: APPROVED
- Applies from: Version 2 AI CIO layer forward

## Purpose

This document permanently freezes the Version 2 AI CIO Dashboard architecture for Trade-Dividend-Bot.

The dashboard is the primary investor-facing interface for portfolio review, capital-allocation ranking, AI CIO recommendations, SGOV notifications, confidence review, candidate comparison, decision history, and deeper analysis.

The governing presentation principle is:

> Present the investor's most important decision first, then provide progressively deeper analysis through optional expandable sections.

The dashboard must remain calm, professional, objective, transparent, evidence-driven, and understandable without requiring knowledge of internal algorithms.

## Permanent First-Page Order

The first page must display sections in this order:

1. Portfolio summary
2. Capital Allocation Rankings
3. Portfolio-level AI CIO Verdict
4. SGOV Notifications
5. Pending investor actions or available overrides
6. Optional analysis links

## Portfolio Summary

The header must display, when available:

- portfolio value
- projected annual income
- projected total wealth
- market regime
- portfolio confidence
- Decision Stability Score
- report date and time
- paper-trade mode status

Missing values must be identified as unavailable, estimated, stale, or incomplete. Missing evidence must never be presented as confirmed evidence.

## Capital Allocation Rankings

Every active deployment of capital must be ranked from strongest to weakest.

The table must use these columns:

| Rank | Strategy | Allocation | Status | Why This Allocation |
|---:|---|---:|---|---|

A strategy may be:

- a single stock
- an ETF
- a growth-plus-income pair
- a multi-asset strategy
- an SGOV reserve allocation

The ranking must show where capital is currently deployed. It must not automatically force a replacement.

A lower-ranked healthy position remains held until an approved sale, lifecycle, protection, or replacement gate authorizes a change.

The `Why This Allocation` link opens the full allocation decision view.

## Portfolio-Level AI CIO Verdict

The portfolio-level verdict must provide one concise natural-language recommendation.

Supported capital actions include:

- KEEP
- INCREASE
- REDUCE
- REPLACE
- WAIT
- PARK IN SGOV
- REENTER
- WATCH

Investor-facing reports must explain the action in complete natural language.

Internal reason codes may remain in JSON, logs, tests, and audit records, but must not replace the visible explanation.

## Required Recommendation Style

The visible recommendation should follow this style:

> **Recommendation: Continue holding AMDW + PLTU.**
>
> Although **AMDW + GGLL** currently has a **2.0-point higher Capital Efficiency Score**, the improvement is **not large enough to justify replacing the current investment**. The current position has a significantly higher **Decision Stability Score**, stronger **Evidence Confidence**, and lower **Expected Downside Risk**. Changing today would increase **Portfolio Turnover** without providing a meaningful improvement in the portfolio's objective of **maximizing long-term total wealth (growth + income)**.
>
> **The alternative will continue to be monitored automatically and will be recommended only if it demonstrates a sustained and meaningful improvement.**

The wording may vary with the evidence, but it must preserve the same clarity, completeness, and natural tone.

## SGOV Notifications

SGOV is both a reserve instrument and a temporary capital-parking destination.

The first page must contain a dedicated SGOV Notifications section.

Each notification must include:

- date
- amount or percentage
- source strategy or instrument
- reason capital moved to SGOV
- whether the move was automatic or investor-approved
- current status
- release condition
- next review

Approved reason categories include:

- earnings lock
- replacement pending
- no qualified opportunity
- mandatory protection rule
- risk reduction
- new reserve cash
- sale proceeds awaiting re-entry
- sale proceeds awaiting redeployment

Example:

> **PLTU allocation moved to SGOV.** The underlying PLTR position entered an earnings-protection window. AMDW remains active because it continues to qualify independently. After earnings, PLTU returns to the candidate pool and must re-earn its allocation. It is not restored automatically.

## Expandable Investor Views

The first page must provide these optional views:

- Why This Allocation
- Compare Candidates
- Analysis Confidence
- Decision History
- AI Analysis

The main page must remain understandable without opening any of them.

## Why This Allocation

This view must show:

- current recommendation
- natural explanation
- current holding or strategy
- strongest challenger
- what changed
- what did not change
- what would invalidate the recommendation
- next review trigger

## Compare Candidates

The comparison table must use three columns:

| Metric | Current | Challenger |
|---|---:|---:|

The current strategy and challenger names must appear at the top of their columns.

Required comparison metrics, when available, include:

- Capital Efficiency Score
- Decision Stability Score
- Expected Annual Income
- Expected Capital Growth
- Total Wealth Projection
- Evidence Confidence
- Market Regime Support
- Sector Strength
- Risk Level
- Maximum Drawdown Estimate
- Portfolio Concentration
- Dividend or Distribution Sustainability
- Earnings Risk
- Portfolio Turnover impact

Winning values may be visually highlighted, but the dashboard must not imply that one metric alone determines the recommendation.

## Analysis Confidence

This view answers:

> How certain is the AI CIO that today's recommendation is supported by reliable evidence?

It must display:

- overall Analysis Confidence
- confidence rating
- evidence quality
- market-data freshness
- missing evidence
- conflicting evidence
- uncertainty factors
- confidence summary

Analysis Confidence must influence behavior:

- very high or high confidence may support autonomous paper action within the Investment Policy Statement
- moderate confidence may support KEEP or WAIT but should defer discretionary rotation
- low confidence must prevent non-essential autonomous portfolio changes

## Decision History

The Decision History must preserve a chronological record of:

- date and time
- recommendation
- action taken
- portfolio before
- portfolio after
- full natural-language explanation
- Decision Stability Score
- Analysis Confidence
- Capital Efficiency Score comparison
- Investment Policy Statement rules applied
- investor approval, veto, defer, or override when applicable

History must be append-only. A revert creates a new decision record and never erases the original action.

## AI Analysis

This is the advanced technical view.

It may include:

- raw component scores
- score weightings
- penalty calculations
- evidence sources
- market-data source state
- confidence calculations
- Decision Stability calculations
- Capital Efficiency calculations
- candidate ranking history
- internal reason codes
- warnings and missing evidence

This view is optional and must not be required to understand the primary recommendation.

## Decision Stability and Anti-Churn

The dashboard must display the full name `Decision Stability Score`.

It measures the likelihood that the current recommendation should remain unchanged under near-term conditions.

It must not independently authorize a sale.

A low Decision Stability Score indicates fragility or transition risk. An approved lifecycle, sale, earnings, protection, or policy gate remains required before action.

The permanent anti-churn rule is:

> Capital Efficiency identifies the strongest opportunity. Decision Stability determines whether the improvement is persistent and meaningful enough to justify changing the portfolio.

## Investor Actions and Autonomous Paper Mode

The paper-trade cycle may operate under approved autonomy levels.

Investor actions may include:

- APPROVE
- REJECT
- DEFER
- VETO
- REQUEST REVERT

At higher paper autonomy levels, actions may be applied automatically within the approved Investment Policy Statement. The investor retains the ability to veto or request a policy-compliant revert.

Mandatory safety actions may park affected capital in SGOV automatically. Automatic restoration to a former holding is prohibited; the former holding must re-enter the candidate pool and requalify.

## Communication Rules

Investor-facing dashboard content must:

- use natural English
- spell out metric names
- explain recommendations
- explain non-actions
- explain changes
- explain uncertainty
- identify estimated, stale, conflicting, and missing evidence
- present the most important conclusion first

Investor-facing dashboard content must not:

- use unexplained abbreviations
- use internal reason codes as the primary explanation
- present raw scores without interpretation
- use sensational or promotional language
- imply certainty when evidence is incomplete

## AI CIO Personality

The AI CIO must communicate as:

- calm
- professional
- objective
- transparent
- evidence-driven
- trustworthy
- decisive without being sensational

## Permanent Dashboard Principle

> Every page must answer the investor's most important question first. Additional information must remain available through optional expandable views.

## Portfolio Philosophy

The AI CIO manages capital allocation, not ticker loyalty.

Every active strategy must continuously earn its allocation according to expected total wealth creation, risk, confidence, stability, concentration, market conditions, and the approved Investment Policy Statement.

## Frozen Interfaces

This freeze governs the investor-facing interfaces produced by:

- AI CIO Decision Engine
- Decision Stability Engine
- Candidate Comparison Engine
- Analysis Confidence Engine
- Decision Journal Engine
- Capital Rotation Engine
- Portfolio Strategy Optimizer
- Executive Dashboard Version 2
- autonomous paper-portfolio management modules

Future enhancements may add information behind the expandable views, but they must not change the frozen first-page hierarchy, core terminology, natural explanation requirements, SGOV notification requirements, or no-abbreviation rule without an explicitly approved new dashboard version.