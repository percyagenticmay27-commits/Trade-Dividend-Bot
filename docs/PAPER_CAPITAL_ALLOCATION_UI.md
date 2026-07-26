# Paper Cash Funding and Capital Allocation UI

## Purpose

Provide an authenticated DigitalOcean UI where the investor controls simulated cash funding and chooses how available paper cash is assigned across strategy plugins recognized by the Enterprise Service Registry.

The UI uses the shared AI CIO Dashboard visual standard: navy gradient header, purple KPI cards, paper-only governance banner, explanation panels, responsive layout, and navigation to Executive and Investor dashboards.

## Complete Workflow

1. Open `/cash`.
2. Review Starting Paper Cash, Available Cash, Reserved Cash, and Allocated Cash.
3. Enter additional simulated capital and confirm the investor action.
4. Append an immutable deposit record to `state/paper_cash_transactions.jsonl`.
5. Update `state/paper_cash_account.json`.
6. Continue to `/allocation`.
7. Query the Enterprise registry for enabled, healthy, paper-compatible strategy plugins.
8. Display only eligible detected strategies.
9. Investor enters the total cash to allocate and assigns dollar amounts across one or more strategies.
10. Validate cash limits, plugin eligibility, and allocation totals.
11. Append an immutable request to `state/paper_allocation_requests.jsonl` with status `PENDING_GOVERNANCE_REVIEW`.

## UI Pages

### Cash Account

- Starting Paper Cash
- Available Cash
- Reserved Cash
- Allocated Cash
- Add Simulated Capital form
- Deposit reason
- Required investor confirmation
- AI CIO commentary
- Link to Strategy Allocation

### Strategy Allocation

- Current available paper cash
- Number of eligible strategies
- Current cash provider
- Dynamically detected strategy cards
- Dollar allocation inputs
- Governed request confirmation

## Provider Architecture

Current default:

```text
CASH_ACCOUNT_PROVIDER=PAPER
```

The paper provider reads:

```text
state/paper_cash_account.json
```

Future live provider:

```text
CASH_ACCOUNT_PROVIDER=ROBINHOOD
```

A future Agentic-to-Robinhood provider may read the broker cash account only after explicit investor authorization. The investor alone controls transition to live mode. Cash synchronization, order execution, withdrawals, transfers, and strategy activation remain separate permissions.

No Robinhood integration is implemented or enabled in Platform V1.

## Safety Boundary

Submitting the cash form changes simulated paper state only. Submitting the allocation form creates a governed paper request only. Neither action contacts a broker, moves real money, places an order, enables a strategy, or changes policy.

## DigitalOcean Runtime

Run behind authenticated HTTPS/Nginx:

```text
python paper_capital_allocation_server.py
```

Local pages:

```text
http://127.0.0.1:8091/cash
http://127.0.0.1:8091/allocation
```

Recommended environment variables:

```text
DIVIDEND_ALLOCATION_HOST=127.0.0.1
DIVIDEND_ALLOCATION_PORT=8091
DIVIDEND_STRATEGY_REGISTRY=results/enterprise_dividend_service_registry.json
DIVIDEND_PAPER_CASH_STATE=state/paper_cash_account.json
DIVIDEND_CASH_TRANSACTION_LOG=state/paper_cash_transactions.jsonl
DIVIDEND_ALLOCATION_REQUEST_LOG=state/paper_allocation_requests.jsonl
DIVIDEND_INVESTOR_ID=default-investor
CASH_ACCOUNT_PROVIDER=PAPER
```

Nginx or Cloudflare Access must provide authentication. The WSGI process must not be exposed directly to the public internet.

## Release Impact

Platform V1 Release remains paused until this module is validated, merged, included in the acceptance test, and added to the release manifest.
