# TradeBot Core Philosophy Version 2.0

## Status

This document is the governing philosophy for the Trade-Dividend-Bot architecture from Version 2.0 forward.

All future scoring, opportunity, pairing, portfolio construction, capital allocation, rebalancing, reporting, and recommendation modules must follow these rules.

The system remains paper-only. It does not place real orders or connect to a brokerage execution interface.

## Mission

Continuously allocate capital to the opportunities expected to convert each dollar into the greatest total wealth under current market conditions, while controlling risk, preserving capital when conditions deteriorate, and remaining free of stock, ETF, sector, or strategy bias.

## Primary Objective

The default objective is **Maximum Growth plus Income**.

The bot does not optimize for the highest dividend yield, the highest distribution rate, or the highest price appreciation in isolation.

It optimizes for total wealth creation:

**Total Wealth = Capital Appreciation + Dividend and Distribution Income + Reinvestment Compounding - Risk and Drawdown Penalties - Concentration Penalties - Trading Friction and Tax Penalties**

Income is valuable because it adds cash flow and compounding power. Growth is valuable because it increases principal. Neither component is allowed to hide deterioration in the other.

## Principle 1 — No Instrument Bias

The bot has no loyalty to any:

- stock
- ETF
- covered-call fund
- leveraged fund
- dividend fund
- growth fund
- sector
- industry
- investment style
- portfolio strategy

Every eligible instrument competes under the same objective: maximum expected growth plus income after risk.

A diversified fund is not automatically preferred because it is diversified. A single-company income fund is not automatically preferred because it has a high distribution. Each must earn its allocation from measurable evidence.

## Principle 2 — Capital Efficiency

Every candidate receives a **Capital Efficiency Score (CES)**.

The CES answers:

> If one dollar is allocated here today, how efficiently is that dollar expected to create total wealth over the selected horizon under current conditions?

The score must consider, at minimum:

- expected capital appreciation
- expected dividend or distribution income
- distribution sustainability
- reinvestment potential
- momentum and trend quality
- company or fund quality
- sector leadership
- market regime support
- volatility
- maximum drawdown
- downside risk
- concentration risk
- correlation with existing holdings
- confidence in the supporting evidence
- tax and turnover effects when available

No single component may dominate merely because it is visually attractive, such as a very high stated yield.

## Principle 3 — Growth and Income Must Be Evaluated Together

A candidate with high income but persistent principal erosion can be inferior to a lower-yield candidate with stronger appreciation.

A candidate with exceptional growth but no income can still be superior when its expected total wealth contribution exceeds the alternatives.

The bot must compare:

- single instruments
- income plus growth pairs
- sector-specific pairs
- diversified strategies
- defensive strategies
- multi-asset portfolios

The winner is the strategy with the best expected total wealth efficiency after risk, not the strategy with the highest yield or the most familiar ticker.

## Principle 4 — Pair and Strategy Competition

Pairs and portfolio strategies must compete directly against their individual components.

For example, the system must be able to compare:

- QQQI alone
- TQQQ alone
- QQQI plus TQQQ
- a sector-specific income instrument plus its underlying growth instrument
- a diversified income fund
- a defensive reserve allocation

A pair is approved only when its expected combined growth plus income, after volatility, drawdown, correlation, and concentration penalties, is superior to the best qualifying single instrument.

The bot must not assume that two holdings are safer or better than one. The combination must prove its advantage quantitatively.

## Principle 5 — Market and Sector Regime Awareness

The most efficient destination for capital changes with market conditions.

During strong technology or semiconductor leadership, a concentrated growth-plus-income strategy may outrank a broad diversified fund.

When technology strength weakens, the preferred destination may rotate toward:

- another leading sector
- a broad-market income strategy
- a defensive dividend strategy
- lower-volatility funds
- Treasury or reserve instruments

The bot must evaluate sector strength, underlying-company strength, broad-market conditions, volatility, and momentum before increasing concentrated exposure.

No sector receives permanent preference.

## Principle 6 — Concentrated Opportunities Require Stronger Evidence

A single-company or single-sector income strategy may create more total wealth than a broad-market fund, but it also carries greater company-specific and sector-specific risk.

Therefore, concentrated candidates require stronger confirmation, including:

- positive underlying-company trend
- positive sector trend
- supportive market regime
- acceptable volatility and drawdown
- acceptable earnings or event risk
- sustainable distribution structure
- adequate liquidity
- high conviction and evidence quality

The bot may allocate to a concentrated opportunity when its expected reward clearly exceeds its additional risk. It must reduce or exit that exposure when the underlying company, sector, or market evidence weakens.

## Principle 7 — Defensive Allocation Is an Active Decision

Moving to SCHD, JEPI, SPYI, SGOV, or another defensive instrument is not a failure to find growth.

It is a valid capital-efficiency decision when the expected return from preserving capital, collecting income, and waiting for stronger conditions exceeds the expected return from remaining in a weakening opportunity.

Cash and reserve instruments compete like every other candidate. They are not automatic permanent allocations, but they may become the highest-efficiency destination during unfavorable regimes.

## Principle 8 — Existing Holdings and New Candidates Use the Same Evidence Standard

The bot must not favor a holding merely because it is already owned.

At every review, current holdings and new candidates are rescored using the same Capital Efficiency model.

However, the bot must also avoid unnecessary score chasing. A higher-ranked candidate alone does not force a sale.

Replacement requires the approved lifecycle and sale gates, including evidence such as:

- weakening conviction
- negative or materially deteriorating momentum
- opportunity score below the approved threshold
- strategy-specific exit signal
- unacceptable risk increase
- broken investment thesis

After a valid sale or reduction signal, the released capital competes among:

- the same instrument at a better re-entry
- stronger existing holdings
- promoted watchlist candidates
- new single-instrument opportunities
- optimized pairs or portfolio strategies
- reserve instruments

This rule preserves the no-bias philosophy while preventing excessive turnover and emotional performance chasing.

## Principle 9 — Minimum Improvement and Anti-Churn Rules

A replacement must provide a meaningful expected improvement after considering:

- the Capital Efficiency Score difference
- transaction friction
- short-term versus long-term tax effects
- confidence in the new evidence
- expected holding period
- concentration impact

The default minimum improvement threshold remains configurable. A small score difference is not sufficient by itself to replace a healthy holding.

## Principle 10 — Allocation Follows Merit

Each stock, fund, pair, or strategy is evaluated on its own merit.

Allocation may be increased, maintained, reduced, replaced, or removed according to:

- Capital Efficiency Score
- rank
- confidence
- risk budget
- market regime
- sector regime
- diversification impact
- available reserve cash

Strong opportunities are rewarded. Weakening opportunities are penalized. No position receives capital because of emotional attachment or historical preference.

## Principle 11 — Income Reinvestment Supports Total Wealth

Income is not treated as an isolated objective.

Dividends and distributions must be reinvested where they are expected to create the most total wealth.

For an approved pair, reinvestment may be split according to the pair’s target allocation or current optimization result. For a qualifying single instrument, income may reinforce that instrument. If a stronger opportunity exists, reinvestment may be redirected subject to portfolio and tax rules.

## Principle 12 — Explain Every Decision

Every recommendation must state:

1. why the selected instrument or strategy ranked highest
2. how expected growth and income contributed to the result
3. what risks reduced the score
4. why the leading alternatives were not selected
5. what changed since the prior review
6. what conditions would cause the allocation to increase, decrease, or exit
7. whether the result uses live, cached, estimated, or missing evidence

The explanation must be auditable and based on recorded inputs.

## Principle 13 — Missing Evidence Is Not Positive Evidence

Missing data must never be interpreted as strength.

The system must identify missing, stale, estimated, and conflicting inputs. Scores derived from incomplete evidence must receive lower confidence and appropriate penalties.

## Principle 14 — Paper-Only Safety Is Permanent

The philosophy governs analysis and paper portfolio management only.

Permanent safety rules:

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- no real order placement
- no Robinhood execution
- read-only market-data access is permitted
- every proposed transaction remains a paper recommendation

## Default Optimization Profile

The default profile is:

**MAXIMUM_TOTAL_WEALTH**

Its goal is to maximize expected growth plus income after risk and friction.

Other profiles may be added later, but they must not alter the default philosophy unless explicitly selected:

- maximum income
- maximum growth
- balanced wealth
- capital preservation

## Required Future Architecture

Future Version 2 modules should include:

1. Capital Efficiency Score Engine
2. Single-Instrument Total Wealth Evaluator
3. Pair Optimization Engine
4. Portfolio Strategy Optimization Engine
5. Sector Leadership Engine
6. Concentration and Correlation Risk Engine
7. Total Wealth Backtester
8. Explainable Recommendation Engine
9. Philosophy Compliance Validator

## Governing Rule

When two choices compete, the bot must ask:

> Which qualifying allocation is expected to make the next dollar work hardest for total wealth under current conditions, after accounting for risk, confidence, concentration, turnover, and taxes?

That question—not ticker familiarity, yield alone, sector preference, or prior ownership—governs the system.
