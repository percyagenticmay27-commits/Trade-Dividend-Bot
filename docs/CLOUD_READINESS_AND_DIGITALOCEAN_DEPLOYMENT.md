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
```

Optional:

```text
DIVIDEND_BOT_TIMEZONE=America/Chicago
DIVIDEND_BOT_RESULTS_DIR=results
DIVIDEND_BOT_LOG_DIR=logs
```

Secrets such as email credentials must be stored outside the repository with permissions limited to the service account. Never commit secrets.

## DigitalOcean Setup

1. Create an Ubuntu droplet with SSH keys and automatic backups.
2. Create a service user, clone the repository, and check out the validated release branch.
3. Create a virtual environment and install only the project's approved dependencies.
4. Export `DIVIDEND_BOT_ENV=paper` in the service environment.
5. Run the cloud-readiness tests before scheduling the bot.
6. Make `start_dividend_bot.sh` executable.
7. Configure a systemd timer or cron entry for the daily paper cycle.

## Example systemd Service

```ini
[Unit]
Description=Trade Dividend Bot Paper Cycle
After=network-online.target

[Service]
Type=oneshot
User=dividendbot
WorkingDirectory=/opt/trade-dividend-bot
Environment=DIVIDEND_BOT_ENV=paper
ExecStart=/opt/trade-dividend-bot/start_dividend_bot.sh
NoNewPrivileges=true
PrivateTmp=true
```

## Example Timer

```ini
[Unit]
Description=Run Trade Dividend Bot daily

[Timer]
OnCalendar=*-*-* 15:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

Set the server timezone explicitly before relying on the timer schedule.

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
