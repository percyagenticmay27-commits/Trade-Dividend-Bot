# AI CIO Portfolio Manager Version 1

## Purpose

The AI CIO Portfolio Manager is the paper-only advisory coordination layer above the Enterprise Executive Dashboard. It produces portfolio-level allocation recommendations from published Enterprise reports without changing strategy logic or creating allocation requests.

## Required Input

- `results/executive_dashboard.json`

## Optional Inputs

- `results/enterprise_health.json`
- a published strategy performance report
- an investor policy JSON document
- available paper-cash amount supplied by the caller

Missing optional inputs create warnings rather than failures.

## Outputs

- `results/ai_cio_portfolio_manager.json`
- `results/ai_cio_portfolio_manager.md`

## Responsibilities

- evaluate Enterprise paper-safety and operating status;
- identify allocation-eligible registered strategies;
- exclude critical, inactive, unready, or unsafe strategies;
- combine health and optional performance evidence into advisory confidence;
- recommend paper allocation percentages and paper amounts;
- preserve a configurable minimum paper-cash reserve;
- enforce a configurable maximum weight per strategy;
- explain exclusions, blockers, and warnings;
- publish recommendations for later investor and governance review.

## Ownership Boundary

The module does not own:

- strategy discovery or registration;
- health calculation;
- performance calculation;
- market-data retrieval;
- investor confirmation;
- allocation-request creation;
- strategy activation;
- scheduling;
- brokerage communication;
- order execution;
- capital movement.

`paper_capital_allocation.py` remains the owner of investor-confirmed, immutable paper allocation requests. The AI CIO Portfolio Manager never calls it automatically.

## Version 1 Recommendation Method

For each eligible strategy:

- health evidence contributes 60% of advisory confidence;
- optional performance evidence contributes 40%;
- missing performance evidence defaults to a neutral score of 50;
- allocation weights are proportional to advisory confidence;
- maximum strategy weight and minimum cash reserve are policy controlled.

This is a deterministic Version 1 advisory method, not an autonomous learning or execution system.

## Status Values

- `ADVISORY_READY`
- `NO_ELIGIBLE_STRATEGIES`
- `BLOCKED`

## Permanent Safety Rules

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- `capital_movement_enabled=False`
- `automatic_allocation_enabled=False`
- advisory only;
- investor approval required;
- governance review required;
- no allocation request created;
- no strategy activation;
- no broker communication or order placement.

## Validation

```bash
python -m py_compile src/dividend_bot/ai_cio_portfolio_manager.py
python -m pytest tests/test_ai_cio_portfolio_manager.py -v
```
