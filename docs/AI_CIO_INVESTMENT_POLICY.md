# AI CIO Investment Policy Statement

## Status

This Investment Policy Statement is the controlling policy for the Trade-Dividend-Bot AI Chief Investment Officer layer.

All recommendations and autonomous paper actions must comply with this document and with `docs/TRADEBOT_CORE_PHILOSOPHY_V2.md`.

## Primary Objective

Maximize expected Total Wealth through the best combination of:

- capital appreciation
- dividend and distribution income
- reinvestment compounding

while reducing expected value for:

- volatility
- drawdown
- downside risk
- concentration
- correlation
- turnover
- tax friction
- missing or stale evidence

## Default Optimization Profile

`MAXIMUM_TOTAL_WEALTH`

The system must not optimize for yield, income, growth, sector popularity, or ticker familiarity in isolation.

## No-Bias Policy

The AI CIO has no permanent preference for any:

- stock
- ETF
- covered-call fund
- leveraged fund
- dividend fund
- growth fund
- sector
- industry
- strategy
- existing holding

Every current holding and new candidate competes under the same evidence standard.

## Capital Efficiency Rule

Every instrument, pair, and strategy must receive a Capital Efficiency Score.

The score estimates how effectively each invested dollar is expected to create Total Wealth under current conditions after risk and friction.

A high distribution rate must not hide principal erosion, weak momentum, poor sustainability, or excessive drawdown.

## Candidate Competition

The system must be able to compare:

- single instruments
- growth-plus-income pairs
- sector-specific strategies
- diversified strategies
- defensive allocations
- reserve instruments
- future multi-asset strategies

A pair or strategy is approved only when it proves an advantage over the best qualifying single instrument after risk, correlation, concentration, and stability are considered.

## Sector Allocation Policy

Sectors organize evidence and risk; they do not receive guaranteed allocations.

The process is:

1. Rank sector leadership and capital-flow evidence.
2. Identify sectors that qualify for capital.
3. Compare the best instruments and strategies inside each qualifying sector.
4. Compare those sector winners against one another.
5. Allocate only where the expected Total Wealth benefit justifies the risk.

A sector may receive zero allocation.

Sector rotation requires persistence. A short-lived score change is not enough.

## Pair and Strategy Lifecycle Policy

Pairs are temporary strategies, not permanent units.

If one member triggers an earnings lock, sale signal, hard drawdown, or disqualification:

- evaluate the unaffected member independently
- retain the unaffected member if it remains qualified
- park the affected allocation in SGOV while alternatives are evaluated
- construct and score any replacement combination before applying it
- replace the full strategy only if the complete strategy thesis has failed or a superior complete strategy qualifies

A former member may re-enter only after the lock or disqualification ends and it wins again under the same scoring rules.

## Earnings Policy

When the underlying company of an instrument enters the configured earnings lock window:

- the affected instrument becomes unavailable for new allocation
- its paper allocation may be parked in SGOV according to the active autonomy level
- the unaffected strategy member is not automatically removed
- no automatic re-entry occurs after earnings
- the instrument must be rescored and requalify

## Sale and Reduction Gates

A higher-ranked candidate alone does not force a sale.

Replacement, reduction, or removal requires an approved gate such as:

- conviction deterioration
- materially negative momentum
- opportunity score below threshold
- strategy-specific exit signal
- hard drawdown threshold
- unacceptable risk increase
- broken investment thesis
- earnings lock
- mandatory protection event

## Minimum Improvement Rule

The default minimum Capital Efficiency Score improvement required for replacement is:

`5.0 points`

The threshold remains configurable.

The comparison must include:

- turnover friction
- short-term and long-term tax effects when available
- concentration impact
- evidence confidence
- expected holding period
- Decision Stability Score

## Decision Stability Policy

The Decision Stability Score is a primary anti-churn control.

It must consider:

- duration of the current recommendation
- score gap to the runner-up
- whether the gap is widening or narrowing
- market-regime persistence
- sector-leadership persistence
- momentum persistence
- evidence freshness and agreement
- proximity to earnings and event locks
- distance from sale and drawdown thresholds

Interpretation:

- `90–100`: Very Stable
- `75–89`: Stable
- `60–74`: Transition Watch
- `40–59`: Unstable
- `0–39`: Critical

A low Decision Stability Score does not independently authorize a sale. It indicates fragility and supports preparation or increased review frequency. Lifecycle and sale gates still control action.

## Concentration Policy

Concentrated single-company, single-sector, and leveraged strategies require stronger evidence than diversified strategies.

They must demonstrate:

- positive underlying-company trend
- positive sector trend
- supportive market regime
- adequate liquidity
- acceptable volatility and drawdown
- acceptable earnings or event risk
- sustainable distribution structure when applicable
- high evidence confidence

Position limits must remain configurable and must be enforced before any autonomous paper action is applied.

## Reserve Policy

SGOV is the default temporary capital-parking instrument unless changed by policy.

Reserve targets are regime-aware:

- strong or supportive markets may use a lower reserve
- weak or deteriorating markets may use a higher reserve
- mandatory protection events may move only the affected allocation to SGOV
- reserve capital may be deployed when a qualifying opportunity appears and all policy gates are satisfied

Reserve is an active capital-efficiency decision, not idle cash.

## Income Reinvestment Policy

Income must be reinvested where it is expected to create the most Total Wealth.

- For a qualifying pair, reinvestment may follow the pair’s approved target allocation.
- For a qualifying single instrument, income may reinforce that instrument.
- If a stronger qualifying opportunity exists, reinvestment may be redirected subject to risk, tax, and stability rules.
- New cash does not automatically force the sale of existing holdings.

## Autonomy Policy

The active autonomy level controls whether a recommendation requires approval or may be applied automatically to the paper portfolio.

Autonomous actions are allowed only when:

- all Investment Policy rules pass
- evidence quality is sufficient
- the action is journaled
- the investor retains veto and revert rights

The default autonomy level remains `LEVEL_1_ADVISOR` until explicitly changed.

## Investor Override Policy

The investor may:

- approve
- reject
- defer
- veto
- request a revert
- lower the autonomy level
- disable autonomous paper changes

An override must be recorded rather than erasing the original recommendation.

## Explanation Policy

Every recommendation must include a complete natural-language explanation.

Investor-facing reports must spell out:

- Capital Efficiency Score
- Decision Stability Score

Internal abbreviations and reason codes must not replace the full explanation.

## Decision Journal Policy

Every applied paper change must preserve an immutable audit record containing:

- before and after allocations
- selected action
- full explanation
- current and runner-up Capital Efficiency Scores
- Decision Stability Score
- portfolio confidence
- policy checks
- evidence freshness
- approval or autonomous authorization
- override and revert history

## Safety Policy

Permanent rules:

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- read-only market-data access is allowed
- no real order placement
- no Robinhood execution
- all transactions are paper recommendations or paper-portfolio updates

## Governing Question

Every decision must answer:

> Which qualifying allocation is expected to make the next dollar work hardest for Total Wealth under current conditions, after accounting for risk, confidence, concentration, turnover, taxes, and Decision Stability?