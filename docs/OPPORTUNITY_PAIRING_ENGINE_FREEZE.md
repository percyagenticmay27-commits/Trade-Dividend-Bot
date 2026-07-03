# OPPORTUNITY_PAIRING_ENGINE_FREEZE

## Purpose

This document records that `opportunity_pairing_engine.py` is complete, verified, and frozen with the Self-Funding ETF Rule update.

## Frozen Purpose

- Ranks total-market income + growth opportunities.
- Compares ETF pairs, covered-call ETFs, dividend ETFs, dividend stocks, leveraged ETFs, and cash shields.
- Ranks opportunities by combined income + growth potential rather than dividend yield alone.

## Self-Funding ETF Rule

Any standalone ETF opportunity must pay some type of dividend or distribution.

The strategy requires ETF opportunities to generate income that can help fund:

- the ETF itself
- a paired leveraged ETF
- a cash shield
- reinvestment
- portfolio rotation

Standalone ETF opportunity types include:

- COVERED_CALL_ETF
- DIVIDEND_ETF
- LEVERAGED_ETF
- CASH_SHIELD

Standalone ETF opportunities must have:

- pays_distribution=True
- distribution_yield greater than 0
- reinvestment_role not equal to NONE

Allowed distribution frequencies:

- DAILY
- WEEKLY
- MONTHLY
- QUARTERLY
- ANNUAL
- VARIABLE
- UNKNOWN

ETF_PAIR exception:

- The income side must pay a distribution.
- The growth side may be a leveraged ETF that does not pay a meaningful distribution.
- ETF_PAIR reinvestment_role defaults to FUND_GROWTH_PAIR.

## Frozen Capabilities

- OpportunityComponent dataclass
- InvestmentOpportunity dataclass
- OpportunityPairingReport dataclass
- build_opportunity_pairing_report()
- validate_opportunity_pairing_report(payload)
- calculate_opportunity_score(opportunity, weights)
- classify_opportunity_recommendation(combined_score)
- compare_opportunities(opportunity_a, opportunity_b)
- rank_opportunities(opportunities)
- write_opportunity_pairing_report_json()
- read_opportunity_pairing_report_json()
- write_opportunity_pairing_report_csv()
- format_opportunity_pairing_report_markdown()
- write_opportunity_pairing_report_markdown()

## Opportunity Types

- ETF_PAIR
- COVERED_CALL_ETF
- DIVIDEND_ETF
- DIVIDEND_STOCK
- LEVERAGED_ETF
- CASH_SHIELD

## Default Weights

- income_score: 18
- growth_score: 22
- total_return_score: 22
- sustainability_score: 14
- risk_score: 8
- liquidity_score: 5
- self_funding_score: 11

Total weight: 100.

## Recommendation Thresholds

- STRONG_OPPORTUNITY: >= 85
- GOOD_OPPORTUNITY: >= 75
- WATCHLIST: >= 60
- HOLD_ONLY: >= 45
- AVOID: below 45

## Verified Examples

- AMDW + AMDL can outrank QQQY when the ETF pair produces the stronger combined score.
- SSO can outrank TSLW + TSLL when the standalone total-return profile is stronger and the standalone ETF satisfies the self-funding rule.
- A leveraged ETF that does not pay a meaningful distribution may be valid only as the growth side of an ETF_PAIR.

## Safety

- Paper-only
- Reporting only
- No brokerage execution
- No Robinhood execution
- No live trading
- No order placement

## Freeze Declaration

`opportunity_pairing_engine.py` is designated as a stable, frozen production interface with the Self-Funding ETF Rule. Future changes should be limited to bug fixes, documented API updates, or schema revisions while preserving backward compatibility whenever practical.
