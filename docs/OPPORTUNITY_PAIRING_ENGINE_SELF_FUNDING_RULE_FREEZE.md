# OPPORTUNITY_PAIRING_ENGINE_SELF_FUNDING_RULE_FREEZE

## Purpose

Document the Self-Funding ETF Rule as a permanent architectural requirement of the Opportunity Pairing Engine.

## Reference

- docs/OPPORTUNITY_PAIRING_ENGINE_FREEZE.md

## Verified Results

python -m py_compile opportunity_pairing_engine.py

PASSED

pytest test_opportunity_pairing_engine.py -v

43 passed

## Verification

- No failed tests
- No tracebacks
- No assertion errors
- Only warning was pytest cache permission denied
- No coverage report was generated

## Purpose of the Rule

The Opportunity Pairing Engine is designed to discover the best total-market investment opportunities that maximize:

- Long-term capital appreciation
- Reliable investment income
- Sustainable reinvestment
- Risk-adjusted total return

The system does not rank opportunities solely by dividend yield.

## Permanent Self-Funding ETF Rule

A standalone ETF opportunity must generate its own recurring income through a dividend or distribution.

The purpose of the distribution is to provide capital that may be used to:

- Reinvest into the ETF itself
- Fund a paired leveraged ETF
- Build a cash shield
- Fund opportunity rotation
- Increase portfolio capital without requiring continuous outside deposits

## Supported Distribution Frequencies

- DAILY
- WEEKLY
- MONTHLY
- QUARTERLY
- ANNUAL
- VARIABLE

## Architecture Rules

### Standalone ETF Opportunities

The following opportunity types must satisfy the Self-Funding ETF Rule:

- COVERED_CALL_ETF
- DIVIDEND_ETF
- LEVERAGED_ETF
- CASH_SHIELD

Requirements:

- pays_distribution=True
- distribution_yield > 0
- valid distribution_frequency
- valid reinvestment_role
- contributes to self_funding_score

### ETF Pair Rule

ETF_PAIR opportunities consist of:

income_symbol

+

growth_symbol

income_symbol:

- must pay a recurring distribution
- funds the overall opportunity

growth_symbol:

- may have no dividend
- serves as the capital appreciation component
- may be leveraged

Default reinvestment role:

FUND_GROWTH_PAIR

## Permanent Investment Philosophy

The Opportunity Pairing Engine evaluates investment opportunities rather than individual securities.

A higher dividend alone is never sufficient.

A higher total return alone is never sufficient.

The preferred opportunity is the one producing the strongest combination of:

- Income
- Growth
- Sustainability
- Risk management
- Self-funding capability

## Examples

### Example 1

AMDW + AMDL

Combined score: 80

QQQY

Combined score: 70

Preferred opportunity:

AMDW + AMDL

### Example 2

TSLW + TSLL

Combined score: 70

SSO

Combined score: 80

Preferred opportunity:

SSO

because its projected total-return opportunity is stronger.

## Future Architectural Rule

Every future discovery engine, ranking engine, portfolio manager, command center, weekly report, monthly report, and dashboard must preserve the Self-Funding ETF Rule unless an explicit architecture revision supersedes it.

## Status

Architecture Rule: FROZEN

Version: v1.0
