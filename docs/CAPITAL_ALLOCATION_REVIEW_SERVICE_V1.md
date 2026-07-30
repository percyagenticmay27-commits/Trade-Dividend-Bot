# Capital Allocation Review Service Version 1

## Purpose

The Capital Allocation Review Service is the governed advisory checkpoint between the AI CIO Portfolio Manager, the Cross-Strategy Risk Engine, and the existing investor-controlled paper allocation request workflow.

It reviews existing reports and produces an advisory decision. It does not allocate capital.

## Required Inputs

- `results/ai_cio_portfolio_manager.json`
- `results/cross_strategy_risk.json`

## Optional Input

- Review policy JSON

Supported policy controls include:

- risk levels eligible for investor review
- whether at least one recommendation is required
- maximum critical findings
- maximum high findings

## Outputs

- `results/capital_allocation_review.json`
- `results/capital_allocation_review.md`

## Decisions

- `APPROVE_FOR_INVESTOR_REVIEW`
- `HOLD`
- `REJECT`

Approval means only that the recommendation may proceed to investor review. It is not an allocation approval and does not create an allocation request.

## Review Checks

- Paper-only safety
- Portfolio Manager blockers
- Recommendation availability
- Cross-strategy risk level
- Critical risk findings
- High risk findings
- Review-policy limits

## Ownership Boundary

`paper_capital_allocation.py` remains the sole owner of investor-confirmed immutable paper allocation requests.

The review service never:

- creates or appends an allocation request
- activates a strategy
- modifies a recommendation
- automatically reallocates paper cash
- moves capital
- contacts a broker
- places an order

## Permanent Safety Constants

```text
paper_trade_mode=True
live_trading_enabled=False
broker_execution_enabled=False
capital_movement_enabled=False
automatic_approval_enabled=False
```

## Governance

Every recommendation continues to require:

- explicit investor approval
- governance review
- a separate request through the existing paper allocation workflow

## Validation

```bash
python -m py_compile src/dividend_bot/capital_allocation_review_service.py
python -m pytest tests/test_capital_allocation_review_service.py -v
```
