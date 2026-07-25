# Cloud Readiness and DigitalOcean Deployment

## Scope

This guide deploys the Trade Dividend Bot as a paper-only scheduled reporting service. It does not enable brokerage communication, order placement, or capital movement.

## Runtime Requirements

- Ubuntu 24.04 LTS or later
- Python 3.11 or later
- Git
- A non-root service account
- Persistent storage for `results/`, `logs/`, `state/`, and `runtime/`

## Environment

Required:

```text
DIVIDEND_BOT_ENV=paper
GMAIL_USER=percyagenticmay27@gmail.com
GMAIL_APP_PASSWORD=<Gmail app password stored outside Git>
REPORT_RECIPIENT=percyagenticmay27@gmail.com
```

Recommended:

```text
DIVIDEND_BOT_TIMEZONE=America/Chicago
DIVIDEND_BOT_RESULTS_DIR=results
DIVIDEND_BOT_LOG_DIR=logs
DIVIDEND_DASHBOARD_BASE_URL=https://dividend.example.com
```

Secrets such as email credentials must be stored outside the repository with permissions limited to the service account. Never commit secrets.

## Report Email Schedule

The report scheduler is checked once per day at 7:00 PM in `DIVIDEND_BOT_TIMEZONE`.

- Weekly report: Friday at 7:00 PM.
- Monthly report: the last calendar day of each month at 7:00 PM.
- When the final day of a month is also Friday, both weekly and monthly emails are sent.
- Emails contain an HTML summary, secure dashboard links when `DIVIDEND_DASHBOARD_BASE_URL` is configured, and any report files that exist at send time.
- The scheduler remains paper-only and cannot invoke brokerage or capital-movement functions.

The scheduler command is:

```text
python scheduled_report_email.py
```

## DigitalOcean Setup

1. Create an Ubuntu droplet with SSH keys and automatic backups.
2. Create a service user, clone the repository, and check out the validated release branch.
3. Create a virtual environment and install only the project's approved dependencies.
4. Store the environment variables in a root-owned or service-account-owned environment file with restrictive permissions.
5. Run the cloud-readiness tests before scheduling the bot.
6. Make `start_dividend_bot.sh` executable.
7. Configure one systemd timer for the daily paper cycle and a second timer for the 7:00 PM report-delivery check.

## Example Daily-Cycle systemd Service

```ini
[Unit]
Description=Trade Dividend Bot Paper Cycle
After=network-online.target

[Service]
Type=oneshot
User=dividendbot
WorkingDirectory=/opt/trade-dividend-bot
EnvironmentFile=/etc/trade-dividend-bot.env
ExecStart=/opt/trade-dividend-bot/start_dividend_bot.sh
NoNewPrivileges=true
PrivateTmp=true
```

## Example Daily-Cycle Timer

```ini
[Unit]
Description=Run Trade Dividend Bot daily

[Timer]
OnCalendar=*-*-* 15:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

## Example Report-Email Service

```ini
[Unit]
Description=Trade Dividend Bot Scheduled Report Email
After=network-online.target

[Service]
Type=oneshot
User=dividendbot
WorkingDirectory=/opt/trade-dividend-bot
EnvironmentFile=/etc/trade-dividend-bot.env
ExecStart=/opt/trade-dividend-bot/.venv/bin/python /opt/trade-dividend-bot/scheduled_report_email.py
NoNewPrivileges=true
PrivateTmp=true
```

## Example Report-Email Timer

```ini
[Unit]
Description=Check Trade Dividend Bot weekly and monthly report schedule

[Timer]
OnCalendar=*-*-* 19:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Set the server timezone explicitly and keep `DIVIDEND_BOT_TIMEZONE` aligned with the intended reporting timezone. The recommended default is `America/Chicago`.

## Dashboard Access

The HTML reporting layer should be served through Nginx over HTTPS and protected with authentication or an identity-aware access service. The scheduled email module uses `DIVIDEND_DASHBOARD_BASE_URL` to create links to:

- Executive Dashboard
- Investor Dashboard
- Strategy Health
- Weekly Reports
- Monthly Reports

The email also attaches available report files so the reports remain accessible if the dashboard site is temporarily unavailable.

## Health Check

Use `src/dividend_bot/cloud_readiness.py` to validate environment variables, runtime directories, required artifacts, Python runtime metadata, and permanent safety boundaries. Write the resulting JSON to `results/cloud_readiness_health.json`.

A deployment is ready for the paper production acceptance test only when the health report is `HEALTHY` and all Phase 13 tests pass.

## Logs and Recovery

- Write structured JSON Lines logs under `logs/`.
- Keep generated reports under `results/`.
- Keep restart and idempotency state under `state/`.
- Retain logs and outputs according to the operator's backup policy.
- After a restart, rerun health validation before the next scheduled paper cycle.

## Safety Boundaries

- `paper_trade_mode=True`
- No Robinhood execution
- No brokerage communication
- No real order placement
- No automatic capital movement
- No automatic policy changes
- Investor approval remains required for advisory outcomes
