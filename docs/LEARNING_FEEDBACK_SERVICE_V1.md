# Learning and Feedback Service Version 1

## Purpose

The Learning and Feedback Service compares prior AI CIO advisory recommendations with later Strategy Performance Analytics results.

It creates governed evidence for human review. It does not retrain a model, alter strategy logic, modify policies, change recommended weights automatically, allocate capital, or execute trades.

## Required Inputs

- Prior AI CIO Portfolio Manager recommendation JSON
- Strategy Performance Analytics JSON

## Outputs

- `results/learning_feedback.json`
- `results/learning_feedback.md`

## Strategy Outcomes

- `OUTPERFORMED`
- `MET_EXPECTATIONS`
- `UNDERPERFORMED`
- `INSUFFICIENT_EVIDENCE`

## Advisory Suggestions

- `CONSIDER_MODEST_INCREASE`
- `MAINTAIN`
- `CONSIDER_MODEST_DECREASE`
- `NO_CHANGE`

Suggestions are never applied automatically.

## Evidence Rules

- Each recommendation is matched to performance evidence by `strategy_id`.
- Missing performance evidence produces `INSUFFICIENT_EVIDENCE`.
- Samples below the configured minimum produce `NO_CHANGE`.
- Strong evidence may suggest a modest increase.
- Stable evidence suggests maintaining the recommendation.
- Weak evidence may suggest a modest decrease.

## Governance Boundaries

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- `automatic_policy_changes_enabled=False`
- `automatic_weight_changes_enabled=False`
- Human governance review is required.
- Investor approval is required before any later allocation request.
- `paper_capital_allocation.py` remains the sole owner of investor-confirmed immutable allocation requests.

## Validation

```bash
python -m py_compile src/dividend_bot/learning_feedback_service.py
python -m pytest tests/test_learning_feedback_service.py -v
```
