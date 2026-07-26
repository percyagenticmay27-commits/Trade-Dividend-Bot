# Trade Dividend Bot Platform V1 Release

## Release Identity

- Release version: `1.0.0`
- Planned Git tag: `dividend-platform-v1.0.0`
- Release type: governed paper-only Dividend platform

## Final Included Scope

- Enterprise Dividend Dashboard
- Enterprise Investor Dashboard
- Governed alerts, reviews, learning, CIO advisory, replacement analysis, and strategy health
- Enterprise daily cycle and service registry/event wiring
- Static HTML AI CIO portal
- Weekly and monthly Gmail delivery
- Paper cash account and append-only cash transaction ledger
- Investor cash-funding UI
- Dynamic registered-strategy discovery
- Governed paper capital-allocation UI and request ledger
- Dashboard and workflow responsibility freeze
- Cloud readiness and paper-production acceptance validation

## Final Release Gates

The release may be merged and tagged only after:

1. `platform_v1_release.py` compiles.
2. `tests/test_platform_v1_release.py` passes.
3. Cloud readiness is `HEALTHY` on DigitalOcean.
4. Paper Production Acceptance is `ACCEPTED`.
5. Hosted HTML portal, `/cash`, and `/allocation` are reachable through protected HTTPS.
6. Weekly Friday 7:00 PM and monthly last-calendar-day 7:00 PM email delivery are verified in `America/Chicago`.
7. Restart recovery preserves paper cash, transaction history, allocation requests, logs, and generated reports.
8. No new dashboard or workflow scope is added before deployment.

## Permanent Safety Boundaries

- Paper trading remains active for Platform V1.
- No Robinhood connection or brokerage execution is enabled.
- No real orders, transfers, withdrawals, or capital movement occur.
- Only the investor may authorize any future live-mode transition.
- Future balance synchronization and order execution remain separate permissions.

## DigitalOcean Outputs

```text
results/
results/html/
logs/
state/
runtime/
```

Required persistent paper artifacts include:

```text
state/paper_cash_account.json
state/paper_cash_transactions.jsonl
state/paper_allocation_requests.jsonl
```

## Email Configuration

Secrets remain outside GitHub:

```text
GMAIL_USER=<gmail address>
GMAIL_APP_PASSWORD=<app password>
REPORT_RECIPIENT=<recipient>
DIVIDEND_BOT_TIMEZONE=America/Chicago
DIVIDEND_DASHBOARD_BASE_URL=https://<protected-dashboard-domain>
```

## Local Validation

```cmd
python -m py_compile src\dividend_bot\platform_v1_release.py
python -m pytest tests\test_platform_v1_release.py -v
```

## Final Tagging Procedure

Only after deployment validation and merge:

```cmd
git checkout main
git pull origin main
git tag -a dividend-platform-v1.0.0 -m "Trade Dividend Bot Platform V1.0.0"
git push origin dividend-platform-v1.0.0
```
