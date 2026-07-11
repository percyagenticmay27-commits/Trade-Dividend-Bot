# AI CIO Design Language Standard

## Status

- Version: 2.0
- Lifecycle: FROZEN SUPPORTING STANDARD
- Applies to: all investor-facing AI CIO reports, dashboards, notifications, journals, and recommendation views

## Purpose

This document defines the permanent design language for the Trade-Dividend-Bot AI CIO experience.

Its purpose is to ensure that every report feels like it came from one calm, professional, evidence-driven Chief Investment Officer rather than from unrelated scoring modules.

## Core Communication Rule

> Speak to the investor in complete natural language. Internal abbreviations, reason codes, and raw calculations may support the system, but they must never replace the investor-facing explanation.

## Investor Questions Every Report Must Answer

Every primary recommendation must answer:

1. What should the investor do?
2. Why is that the preferred action today?
3. What current strategy was compared with which challenger?
4. What would cause the recommendation to change?
5. How reliable and stable is the supporting evidence?

## Voice and Tone

The AI CIO voice must be:

- calm
- concise without being cryptic
- professional
- objective
- transparent
- confident when evidence supports confidence
- cautious when evidence is incomplete
- free of hype, fear, urgency, and promotional language

Approved style:

> Based on the available evidence, no portfolio change is recommended today.

Prohibited style:

> Huge opportunity. Buy now before it runs.

## Required Metric Names

Investor-facing reports must use full metric names.

Use:

- Capital Efficiency Score
- Decision Stability Score
- Analysis Confidence
- Evidence Confidence
- Expected Downside Risk
- Expected Annual Income
- Expected Capital Growth
- Total Wealth Projection
- Market Regime Support
- Sector Strength
- Portfolio Turnover
- Maximum Drawdown Estimate
- Portfolio Concentration
- Dividend Sustainability
- Distribution Sustainability

Do not use unexplained abbreviations such as:

- CES
- DSS
- IPS
- MR
- CF
- DD

The full term may be followed by an abbreviation only in an advanced technical view after the full name has been introduced.

## Primary Recommendation Format

The primary recommendation must begin with a direct action statement.

Example:

> **Recommendation: Continue holding AMDW + PLTU.**

The explanation must then identify the strongest challenger, the meaningful score difference, and why the change is or is not justified.

Preferred style:

> Although **AMDW + GGLL** currently has a **2.0-point higher Capital Efficiency Score**, the improvement is **not large enough to justify replacing the current investment**. The current position has a significantly higher **Decision Stability Score**, stronger **Evidence Confidence**, and lower **Expected Downside Risk**. Changing today would increase **Portfolio Turnover** without providing a meaningful improvement in the portfolio's objective of **maximizing long-term total wealth (growth + income)**.

The explanation should conclude by stating how the alternative will be handled:

> **The alternative will continue to be monitored automatically and will be recommended only if it demonstrates a sustained and meaningful improvement.**

## Explanation Requirements

A natural explanation must cover the factors that materially influenced the decision, which may include:

- expected growth
- expected income
- risk-adjusted total wealth
- market regime
- sector leadership
- momentum
- earnings risk
- Decision Stability Score
- Evidence Confidence
- downside risk
- concentration
- turnover and tax effects
- mandatory protection rules
- replacement threshold

The explanation must not be reduced to an arbitrary bullet limit.

Bullets may be used for supporting facts, but the central explanation must read as a coherent portfolio-management decision.

## Explain Non-Action

The AI CIO must explain why it did not act.

Examples:

- the challenger did not exceed the required improvement threshold
- the score advantage has not persisted long enough
- evidence confidence is insufficient
- the current holding remains healthy
- turnover and risk outweigh the projected benefit
- a sale or lifecycle gate has not been triggered

A higher-ranked candidate alone is not a complete explanation for changing the portfolio.

## Explain Action

When recommending or applying a change, the explanation must identify:

- what changed
- why the current allocation no longer qualifies or no longer deserves its full allocation
- which protection, lifecycle, sale, or policy rule authorized the action
- why the replacement is the strongest qualified destination
- why SGOV was or was not used temporarily
- the expected improvement after risk and friction
- the next review condition

## Pair-Break Explanation

When one member of a pair is affected, the explanation must state whether:

- only the affected member moved to SGOV
- a qualified replacement filled the vacant role
- the entire strategy was dissolved because the remaining member no longer qualified
- the entire pair was replaced by a stronger approved strategy

The report must never imply that a pair member was restored automatically after an earnings lock or sale event. Former holdings must requalify.

## SGOV Language

SGOV must be described by purpose, not merely as a ticker.

Approved descriptions include:

- temporary capital parking
- reserve allocation
- earnings-protection allocation
- sale proceeds awaiting re-entry review
- capital awaiting a qualified replacement
- capital-preservation allocation

Every SGOV notification must explain source, reason, status, release condition, and next review.

## Compare Candidates View

The table must use:

| Metric | Current | Challenger |
|---|---:|---:|

The current and challenger strategy names must appear at the top of their columns.

The table must show both current and challenger values for every available metric. A challenger value must never appear without the corresponding current value.

Winning values may be highlighted, but the recommendation explanation must clarify that the final decision reflects the complete total-wealth and policy evaluation rather than a single winning metric.

## Analysis Confidence View

The visible title is `Analysis Confidence`.

This view must explain:

- overall confidence
- evidence quality
- data freshness
- missing data
- conflicting evidence
- uncertainty factors
- whether confidence is sufficient for autonomous paper action

It must not merely display a percentage.

## Decision Stability Language

Always write `Decision Stability Score` in investor-facing content.

Preferred interpretation:

- 90–100: Very Stable
- 75–89: Stable
- 60–74: Transition Watch
- 40–59: Unstable
- 0–39: Critical

The explanation must clarify that a low score indicates fragility, not an automatic sale instruction.

## Capital Efficiency Language

Always write `Capital Efficiency Score` in investor-facing content.

It measures how effectively an allocation is expected to convert invested capital into total wealth through growth plus income after risk, concentration, confidence, and friction.

Do not describe the score as a guaranteed return or percentile unless the underlying implementation explicitly supports that interpretation.

## Navigation Labels

Use these standard labels:

- Why This Allocation
- Compare Candidates
- Analysis Confidence
- Decision History
- AI Analysis

Avoid vague labels such as:

- More
- Technical
- Debug
- Raw
- Miscellaneous

## Visual Hierarchy

The first visible item on every decision page must be the recommendation.

The supporting order is:

1. Recommendation
2. Natural explanation
3. Today's action
4. Current-versus-challenger comparison link
5. Analysis Confidence link
6. Decision History link
7. AI Analysis link

## Bold Emphasis

Bold text should emphasize the specific ideas the investor must notice:

- recommended action
- current strategy
- challenger strategy
- meaningful score difference
- whether the threshold was or was not met
- Decision Stability Score
- Evidence Confidence
- Expected Downside Risk
- Portfolio Turnover
- total wealth objective

Bold emphasis must remain selective. Entire paragraphs must not be bold.

## Uncertainty Language

When evidence is incomplete, use direct language:

> Analysis Confidence is moderate because sector evidence is incomplete and one market-data source is stale. No discretionary portfolio change is authorized until the evidence improves.

Never hide uncertainty behind a high-level recommendation.

## Autonomous-Mode Language

When an autonomous paper action occurs, the report must say:

- what was applied
- why it was authorized
- which Investment Policy Statement rule permitted it
- whether an investor veto or revert is available

Example:

> The affected PLTU allocation was moved automatically to SGOV because the underlying PLTR position entered its approved earnings-protection window. This action was authorized by the Investment Policy Statement. Investor veto remains available, but PLTU cannot be restored while the earnings lock remains active.

## Decision History Language

Decision-history entries must be understandable without opening technical logs.

Each entry must state:

- action
- affected allocation
- natural reason
- important score or evidence change
- approval or autonomy state
- next review

## Technical Detail Separation

Raw calculations, weightings, codes, and formulas belong in `AI Analysis`.

They must not clutter the executive recommendation.

The investor must be able to understand the decision without opening the technical view.

## Prohibited Communication Patterns

Do not:

- lead with internal codes
- show unexplained abbreviations
- imply guaranteed returns
- use exaggerated certainty
- use promotional language
- hide missing evidence
- recommend change solely because rank changed
- describe SGOV movement without its cause and release condition
- present the challenger without the current comparison value
- present a score without interpretation

## Permanent Design Principle

> Every investor-facing page must communicate the decision first, the reason second, the comparison third, and the technical evidence only on request.

## Change Control

This standard is frozen for Version 2. Future refinements may improve readability and accessibility, but changes to terminology, tone, navigation labels, explanation structure, or the no-unexplained-abbreviation rule require an explicitly approved new design-language version.