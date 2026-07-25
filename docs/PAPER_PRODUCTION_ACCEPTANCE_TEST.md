# Paper Production Acceptance Test

## Purpose

Validate the complete deployed Trade Dividend Bot workflow using realistic paper-only artifacts before Platform V1 release.

## Acceptance Scope

The acceptance report verifies:

- Executive dashboard JSON and Markdown outputs
- Hosted HTML portal and core dashboard pages
- Structured JSON Lines logs
- Persistent paper-state recovery data
- Scheduled Gmail delivery through either a controlled dry run or confirmed sent message
- Restart and recovery validation
- Permanent paper-only governance boundaries

## Required Result

The generated acceptance report must have:

```text
status=ACCEPTED
failed_checks=0
paper_trade_mode=True
live_trading_enabled=False
broker_execution_enabled=False
```

## Required Artifacts

```text
results/enterprise_dividend_dashboard.json
results/enterprise_dividend_dashboard.md
results/html/index.html
results/html/executive_dashboard.html
results/html/investor_dashboard.html
results/html/strategy_health.html
logs/dividend_bot.jsonl
state/paper_state.json
```

## Email Validation

The email gate passes when the operator records either:

```text
SENT
DRY_RUN_PASSED
```

A real Gmail password must never be committed to the repository.

## Restart Recovery Validation

The operator must stop and restart the paper service, rerun cloud health validation, and confirm that persistent state is loaded without duplicate records or unsafe actions.

## Safety Boundaries

- Paper trading only
- No Robinhood execution
- No brokerage communication
- No real order placement
- No capital movement
- No automatic policy changes

## Local Validation

```cmd
python -m py_compile src\dividend_bot\paper_production_acceptance.py
python -m pytest tests\test_paper_production_acceptance.py -v
```
