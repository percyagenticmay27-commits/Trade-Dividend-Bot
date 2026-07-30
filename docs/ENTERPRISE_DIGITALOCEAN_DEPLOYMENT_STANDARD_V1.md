# Enterprise DigitalOcean Deployment Standard Version 1

## Purpose

This document is the shared deployment standard for Enterprise AI CIO strategy repositories deployed to DigitalOcean. It is authoritative for the Dividend Bot, Swing Bot, and future strategy plugins.

Repository-specific runbooks may add implementation details, but they must not contradict this standard.

## Deployment Architecture

The initial supported architecture is:

```text
DigitalOcean Project: AI CIO Portfolio System
└── Droplet: ai-cio-platform
    └── /home/tradebot/
        ├── Trade-Dividend-Bot/
        ├── Trade-Swing-Bot/
        └── future-strategy-repositories/
```

Rules:

- Repositories remain separate.
- Each repository has its own virtual environment.
- Each repository has its own state, results, logs, and runtime directories.
- Each repository has separate systemd units.
- Strategy repositories communicate through frozen Enterprise contracts and registry outputs.
- One strategy repository must never import another strategy repository's production code directly.

## Safety Requirements

Every deployed strategy must preserve:

```text
paper_trade_mode=true
live_trading_enabled=false
broker_execution_enabled=false
capital_movement_enabled=false
```

No DigitalOcean deployment step may enable brokerage execution, real orders, or live capital movement.

## Server User and Ownership

Production repositories run under:

```text
User=tradebot
Group=tradebot
```

Repository ownership must be:

```bash
chown -R tradebot:tradebot /home/tradebot/<repository>
```

Do not run normal bot cycles as `root`.

## GitHub Access

Use one read-only GitHub deploy key per private repository.

Rules:

- Leave **Allow write access** unchecked.
- The server may clone, fetch, and pull.
- The server must not push production changes to GitHub.
- Separate deploy keys should use separate SSH aliases.

Example SSH configuration:

```text
Host github-dividend
    HostName github.com
    User git
    IdentityFile /home/tradebot/.ssh/id_ed25519
    IdentitiesOnly yes

Host github-swing
    HostName github.com
    User git
    IdentityFile /home/tradebot/.ssh/id_ed25519_swing
    IdentitiesOnly yes
```

Required permissions:

```bash
chmod 700 /home/tradebot/.ssh
chmod 600 /home/tradebot/.ssh/config
chmod 600 /home/tradebot/.ssh/id_ed25519*
chmod 644 /home/tradebot/.ssh/*.pub
```

## Repository Isolation

Each repository uses its own path:

```text
/home/tradebot/Trade-Dividend-Bot
/home/tradebot/Trade-Swing-Bot
```

Each repository uses its own virtual environment:

```text
/home/tradebot/Trade-Dividend-Bot/.venv
/home/tradebot/Trade-Swing-Bot/.venv
```

Each repository uses its own runtime outputs:

```text
state/
results/
logs/
runtime/
```

A strategy must not write to another strategy's state or result directories.

## Backup Before Deployment or Update

Before a material deployment or update:

```bash
cd /home/tradebot
BACKUP_NAME="<repository>-backup-$(date +%Y%m%d-%H%M%S)"
cp -a <repository> "$BACKUP_NAME"
tar -czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
ls -lh "$BACKUP_NAME.tar.gz"
```

For a repository with local runtime changes, also preserve the Git state:

```bash
cd /home/tradebot/<repository>
sudo -u tradebot git stash push --include-untracked \
  -m "DigitalOcean runtime state before update $(date +%Y%m%d-%H%M%S)"
```

Do not automatically run `git stash pop` after an update. Restore persistent data selectively.

## Standard Clone Procedure

```bash
cd /home/tradebot
sudo -u tradebot git clone \
  git@<repository-ssh-alias>:percyagenticmay27-commits/<repository>.git
```

Verify:

```bash
cd /home/tradebot/<repository>
sudo -u tradebot git status
sudo -u tradebot git branch --show-current
sudo -u tradebot git log --oneline -5
```

## Virtual Environment

Create one environment per repository:

```bash
cd /home/tradebot/<repository>
sudo -u tradebot python3 -m venv .venv
sudo -u tradebot .venv/bin/python -m pip install --upgrade pip
sudo -u tradebot .venv/bin/python -m pip install -r requirements.txt
```

Do not share the Dividend and Swing environments.

## Dependency Change Rule

Before installing dependencies during an update:

```bash
git diff <previous-ref>..HEAD -- requirements.txt pyproject.toml setup.py
```

If dependency files did not change, do not reinstall packages solely because production code changed.

If dependency files changed:

```bash
sudo -u tradebot .venv/bin/python -m pip install -r requirements.txt
```

## Validation Before Service Activation

At minimum:

```bash
sudo -u tradebot .venv/bin/python -m compileall src
sudo -u tradebot .venv/bin/python -m pytest -v
```

Repository-specific targeted tests must also pass, including:

- paper-only safety;
- Enterprise plugin compatibility;
- registry publishing;
- health and status contracts;
- AI CIO discovery;
- runtime output validation.

## Environment Files

Repository environment files must be isolated and protected:

```bash
chown tradebot:tradebot /home/tradebot/<repository>/.env
chmod 600 /home/tradebot/<repository>/.env
```

Do not commit secrets, app passwords, tokens, deploy-key private material, or production `.env` contents.

Use only environment variable names already defined by the repository contract.

## systemd Standard

Each strategy receives distinct systemd units.

Examples:

```text
dividend-bot.service
dividend-bot.timer
dividend-allocation.service

swing-bot.service
swing-bot.timer
swing-enterprise-runtime.service
```

A service must define:

```text
User=tradebot
Group=tradebot
WorkingDirectory=/home/tradebot/<repository>
EnvironmentFile=/home/tradebot/<repository>/.env
ExecStart=/home/tradebot/<repository>/.venv/bin/python <official-entry-point>
```

After unit changes:

```bash
systemctl daemon-reload
systemctl start <service>
systemctl status <service> --no-pager -l
```

Enable a timer only after a successful manual paper cycle.

## Standard Update Procedure

Stop only the affected timer or service when necessary.

```bash
cd /home/tradebot/<repository>
sudo -u tradebot git fetch origin
sudo -u tradebot git switch main
sudo -u tradebot git pull --ff-only origin main
sudo -u tradebot git rev-list --left-right --count HEAD...origin/main
```

Expected comparison:

```text
0    0
```

Then compile, test, correct ownership, and restart only the affected service.

## Logs and Diagnostics

Use both repository logs and systemd journals:

```bash
journalctl -u <service> -n 100 --no-pager
journalctl -u <timer> -n 50 --no-pager
```

Do not expose Python service ports directly to the public internet. Browser access must use authenticated HTTPS through Nginx or an equivalent reverse proxy.

## Enterprise AI CIO Integration

Each strategy publishes its own Enterprise-compatible contracts, including as applicable:

- strategy registry record;
- health and status record;
- capabilities;
- evidence and reporting outputs;
- paper-only safety flags.

The AI CIO consumes these contracts through a shared or consolidated registry. It must not require strategy repositories to share source code, virtual environments, or mutable runtime state.

## Recovery

If an update fails:

1. stop the affected service or timer;
2. preserve current logs;
3. restore the pre-update repository backup or reset to the previously validated commit;
4. restore only required persistent state;
5. rerun compile and targeted tests;
6. perform one manual paper cycle;
7. restart the timer only after validation.

## Repository-Specific Supplements

Each repository should maintain a small supplement documenting only:

- repository path;
- SSH alias;
- official entry point;
- required environment variables;
- systemd unit names;
- schedule;
- output files;
- repository-specific validation commands.

## Permanent Rules

- Same DigitalOcean Project: allowed.
- Same Droplet: allowed when resources are sufficient.
- Same repository: prohibited.
- Same virtual environment: prohibited.
- Shared mutable state directory: prohibited.
- Shared Enterprise contracts and AI CIO dashboard: required.
- Real brokerage execution: prohibited for the current paper-only platform.
