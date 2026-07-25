# Trade Dividend Bot Platform V1 Release

## Release Identity

- Release version: `1.0.0`
- Planned Git tag: `dividend-platform-v1.0.0`
- Release type: paper-only governed Dividend platform

## Release Gates

The release may be tagged only after all of the following are confirmed:

1. Platform V1 freeze documentation is present and unchanged except for approved maintenance updates.
2. Cloud readiness status is `HEALTHY`.
3. Paper production acceptance status is `ACCEPTED`.
4. The complete release validation suite passes locally.
5. DigitalOcean environment variables and secret storage are configured outside the repository.
6. Weekly Friday 7:00 PM and last-calendar-day monthly 7:00 PM email schedules are configured in `America/Chicago` unless explicitly changed.
7. Nginx serves the generated `results/html/` portal through HTTPS and access protection.

## Included Platform V1 Capabilities

- Enterprise Dividend Dashboard
- Enterprise Investor Dashboard
- Governed Dividend Alerts
- Dividend Review Workflow
- Append-only Dividend Learning
- Enterprise Dividend CIO Advisory
- Dividend Replacement Analysis
- Dividend Strategy Health
- Enterprise Daily Cycle
- Service Registry and Event Wiring
- End-to-End Integration Tests
- Platform Freeze
- Cloud Readiness and DigitalOcean deployment support
- Scheduled weekly and monthly Gmail delivery
- Static HTML AI CIO portal
- Paper Production Acceptance validation

## Permanent Safety Boundaries

- `paper_trade_mode=True`
- No Robinhood execution
- No brokerage communication
- No real order placement
- No automatic capital movement
- No automatic policy changes
- CIO outputs remain advisory
- Investor approval remains required

## Deployment Outputs

The DigitalOcean deployment must preserve:

- `results/` for JSON and Markdown reports
- `results/html/` for the hosted AI CIO portal
- `logs/` for structured JSON Lines logs
- `state/` for restart and idempotency state
- `runtime/` for runtime health artifacts

## Email Delivery

Required environment values:

```text
GMAIL_USER=percyagenticmay27@gmail.com
GMAIL_APP_PASSWORD=<stored outside GitHub>
REPORT_RECIPIENT=percyagenticmay27@gmail.com
DIVIDEND_BOT_TIMEZONE=America/Chicago
DIVIDEND_DASHBOARD_BASE_URL=https://<protected-dashboard-domain>
```

Weekly delivery occurs Friday at 7:00 PM. Monthly delivery occurs at 7:00 PM on the last calendar day of each month. When both conditions occur on the same date, both reports are due.

## Deferred Version 2 Scope

- Swing strategy integration
- Options strategy integration
- Futures strategy integration
- Live brokerage execution
- Automatic investor approvals
- Automatic policy changes

## Tagging Procedure

After PR validation and merge into `main`, run in Git CMD:

```cmd
git checkout main
git pull origin main
git tag -a dividend-platform-v1.0.0 -m "Trade Dividend Bot Platform V1.0.0"
git push origin dividend-platform-v1.0.0
```

Do not create or push the release tag before the release branch tests pass and the pull request is merged.
