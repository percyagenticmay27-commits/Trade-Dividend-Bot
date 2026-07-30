# Strategy Performance Analytics Version 1

## Purpose

Provide a read-only Enterprise analytics layer for comparing historical paper-strategy performance. The service summarizes return, win rate, drawdown, sample size, consistency, and optional AI CIO recommended weights.

## Inputs

Required:

- A strategy performance JSON document containing a list under `strategies`, `strategy_performance`, `performance`, or `results`.

Optional:

- `results/ai_cio_portfolio_manager.json`

Missing optional inputs create warnings.

## Outputs

- `results/strategy_performance_analytics.json`
- `results/strategy_performance_analytics.md`

## Version 1 Metrics

Each strategy receives:

- total return percentage
- win rate percentage
- maximum drawdown percentage
- sample size
- consistency score
- performance score from 0 to 100
- classification: `STRONG`, `STABLE`, `WATCH`, or `WEAK`
- warning flags for limited evidence, elevated drawdown, and negative return

## Ownership Boundaries

This service does not:

- change strategy logic
- schedule strategy runs
- change AI CIO recommendations
- create allocation requests
- activate strategies
- retrieve market data
- communicate with a broker
- move capital
- place orders

The service is advisory and read-only. Investor approval remains required for any allocation workflow.

## Permanent Safety Rules

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- `capital_movement_enabled=False`

## Validation

```bash
python -m py_compile src/dividend_bot/strategy_performance_analytics.py
python -m pytest tests/test_strategy_performance_analytics.py -v
```
