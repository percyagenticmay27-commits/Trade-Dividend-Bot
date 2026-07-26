# Dashboard and Workflow Scope Freeze

## Purpose

Prevent duplicated features, circular development, and scope creep before DigitalOcean deployment.

This document freezes the responsibility of every Platform V1 user interface. Existing calculations and source records remain the single source of truth; dashboards may summarize or link to them but must not reimplement them.

## Frozen Responsibilities

### Enterprise AI CIO Portal

Platform-level navigation and status only:

- registered services and strategy plugins
- platform health and readiness
- enterprise cash and allocation totals
- pending investor approvals
- links to dashboards, reports, and workflows

It must not reproduce detailed portfolio, dividend, or strategy analytics.

### Executive Dashboard

Read-only executive summary of the governed Dividend platform:

- system and reporting status
- aggregate income, forecast, risk, alert, review, and strategy-health summaries
- major exceptions and suggested review actions

It must not become a second Investor Dashboard or an allocation workflow.

### Investor Dashboard

Investor-facing portfolio summary:

- portfolio value and performance
- income, yield, cash, allocation, and risk summaries
- strategy status and investor review items
- approval and override requests

It must not execute decisions, move capital, duplicate platform operations monitoring, or reproduce full strategy-specific analytics.

### Dividend Strategy Dashboard

Dividend-specific analytics only:

- dividend income and forecasts
- yield and yield on cost
- payment consistency and calendar
- dividend growth, cuts, suspensions, and coverage
- Dividend strategy health and review items

Future strategy plugins must own their own separate dashboards.

### Cash Account Workflow

Investor-controlled funding workflow only:

- display persistent paper cash balances
- accept investor-supplied simulated deposits
- append paper cash transaction records
- preserve investor-only authorization for any future live-mode transition

### Allocation Center

Investor-controlled allocation workflow only:

- read available cash from the selected cash provider
- discover eligible strategies from the Enterprise Service Registry
- accept investor allocation selections
- validate totals and eligibility
- append governed allocation requests

It must not duplicate strategy analysis or automatically activate strategies.

### Plugin Discovery

Registry metadata only:

- installed or available strategy plugins
- version, status, health, capabilities, and dashboard link

It must not allocate cash or reproduce strategy performance reports.

## Shared Data Rule

Cash, portfolio, strategy, alert, review, learning, and approval values must be calculated once by their owning service. Every dashboard and workflow must read those outputs rather than creating competing calculations.

## Deployment Gate

Before Platform V1 release:

1. No new dashboard or workflow may be added without replacing an explicitly identified gap.
2. Existing pages may receive bug fixes, deployment wiring, security, accessibility, and presentation maintenance only.
3. New investment strategies remain deferred until the Dividend production workflow is stable.
4. The remaining path is acceptance validation, release validation, DigitalOcean deployment, scheduler verification, email verification, restart recovery, and release tagging.

## Permanent Safety Boundary

Platform V1 remains paper-only. Only the investor may authorize a future transition to live mode. Robinhood or Agentic integration is deferred and cannot be enabled by dashboards, workflows, scheduled jobs, or advisory services.