# Cross-Strategy Risk Engine Version 1

## Purpose

The Cross-Strategy Risk Engine is a read-only, advisory AI CIO service. It evaluates portfolio-level risk across strategy recommendations without changing allocations, activating strategies, moving capital, or placing orders.

## Required Input

- `results/ai_cio_portfolio_manager.json`

## Optional Inputs

- `results/enterprise_health.json`
- cross-strategy correlation evidence JSON
- investor risk-policy JSON

Missing or invalid optional inputs create warnings rather than failures.

## Outputs

- `results/cross_strategy_risk.json`
- `results/cross_strategy_risk.md`

## Version 1 Risk Checks

- Per-strategy concentration against a policy maximum
- Exposure to degraded, critical, offline, or unsafe strategies
- Pair-correlation threshold checks when correlation evidence is supplied
- Minimum paper-cash reserve
- Total recommended weight above 100 percent
- Missing correlation-evidence warning when multiple strategies are recommended

## Risk Status

- `ACCEPTABLE`
- `WATCH`
- `HIGH`
- `CRITICAL`

## Ownership Boundary

This module reports risk only. It does not modify the AI CIO recommendation and does not create an investor allocation request. `paper_capital_allocation.py` remains the owner of investor-confirmed immutable allocation requests.

## Permanent Safety Rules

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- `capital_movement_enabled=False`
- advisory only
- no automatic reallocation
- investor approval required
- governance review required
- no private strategy imports
- no broker or provider calls

## Validation

```bash
python -m py_compile src/dividend_bot/cross_strategy_risk_engine.py
python -m pytest tests/test_cross_strategy_risk_engine.py -v
```
