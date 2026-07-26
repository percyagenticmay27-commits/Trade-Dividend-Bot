# Paper Production Acceptance Test

## Purpose

Validate the complete deployed Trade Dividend Bot workflow using realistic paper-only artifacts before Platform V1 release.

## Acceptance Scope

The acceptance report verifies:

- Executive dashboard JSON and Markdown outputs
- Hosted HTML portal and core dashboard pages
- Structured JSON Lines logs
- Persistent paper-state recovery data
- Canonical investor paper cash account state
- Append-only paper cash transaction history
- Dynamic strategy registry availability
- Investor-controlled cash funding UI
- Investor-controlled strategy allocation UI
- Immutable allocation request history
- Scheduled Gmail delivery through either a controlled dry run or confirmed sent message
- Restart and recovery validation
- Permanent paper-only governance boundaries

## Required Result

```text
status=ACCEPTED
failed_checks=0
paper_trade_mode=True
live_trading_enabled=False
broker_execution_enabled=False
capital_movement_enabled=False
investor_controls_live_mode=True
```

## Required Artifacts

```text
results/enterprise_dividend_dashboard.json
results/enterprise_dividend_dashboard.md
results/html/index.html
results/html/executive_dashboard.html
results/html/investor_dashboard.html
results/html/strategy_health.html
results/enterprise_dividend_service_registry.json
logs/dividend_bot.jsonl
state/paper_state.json
state/paper_cash_account.json
state/paper_cash_transactions.jsonl
state/paper_allocation_requests.jsonl
```

## Investor Capital Workflow Gate

Acceptance requires a validated end-to-end paper workflow:

1. Investor enters simulated cash through the AI CIO Cash Account page.
2. The canonical paper cash account is updated.
3. An append-only paper cash transaction is recorded.
4. The platform discovers eligible strategies from the Enterprise Service Registry.
5. The investor assigns available paper cash across detected strategies.
6. The platform records an immutable request with `PENDING_GOVERNANCE_REVIEW`.
7. No brokerage communication, cash movement, strategy activation, or order placement occurs.

## Email Validation

The email gate passes when the operator records either `SENT` or `DRY_RUN_PASSED`. A real Gmail password must never be committed to the repository.

## Restart Recovery Validation

The operator must stop and restart the paper service, rerun cloud health validation, and confirm that cash state, transaction history, and allocation request history load without duplicate records or unsafe actions.

## Safety Boundaries

- Paper trading only
- Investor alone controls any future live-mode authorization
- No Robinhood execution in Platform V1
- No brokerage communication
- No real order placement
- No capital movement
- No automatic policy changes

## Local Validation

```cmd
python -m py_compile src\dividend_bot\paper_production_acceptance.py
python -m pytest tests\test_paper_production_acceptance.py -v
```
