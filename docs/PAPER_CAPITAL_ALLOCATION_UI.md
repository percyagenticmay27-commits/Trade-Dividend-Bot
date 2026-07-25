# Paper Capital Allocation UI

## Purpose

Provide an authenticated DigitalOcean UI where the investor enters an amount of available paper cash and selects from strategy plugins currently recognized by the Enterprise registry.

## Workflow

1. Read the current paper cash account.
2. Query the registry for enabled, paper-compatible strategy plugins.
3. Display only eligible strategies.
4. Investor enters the total paper cash amount to assign.
5. Investor assigns dollar amounts across one or more strategies.
6. The system validates cash limits, plugin status, paper compatibility, and allocation totals.
7. An immutable request is appended to `state/paper_allocation_requests.jsonl` with status `PENDING_GOVERNANCE_REVIEW`.

## Safety Boundary

Submitting the form does not move cash, place an order, contact a broker, enable a strategy, or change policy. It creates a governed paper-allocation request only.

## DigitalOcean Runtime

Run the local WSGI service behind authenticated HTTPS/Nginx:

```text
python paper_capital_allocation_server.py
```

Default local endpoint:

```text
http://127.0.0.1:8091/allocation
```

Recommended environment variables:

```text
DIVIDEND_ALLOCATION_HOST=127.0.0.1
DIVIDEND_ALLOCATION_PORT=8091
DIVIDEND_STRATEGY_REGISTRY=results/enterprise_dividend_service_registry.json
DIVIDEND_PAPER_CASH_STATE=state/paper_cash_account.json
DIVIDEND_ALLOCATION_REQUEST_LOG=state/paper_allocation_requests.jsonl
DIVIDEND_INVESTOR_ID=default-investor
```

Nginx or Cloudflare Access must provide authentication. The WSGI process should not be exposed directly to the public internet.

## Release Impact

Platform V1 Release remains paused until this module is validated, merged, included in the acceptance test, and added to the release manifest.
