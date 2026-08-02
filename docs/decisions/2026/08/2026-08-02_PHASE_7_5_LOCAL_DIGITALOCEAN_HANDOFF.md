# Phase 7.5 — Local-to-DigitalOcean Validation Handoff

## Decision

Phase 7.5 makes the production-validation boundary explicit. Local Windows
validation must first produce accepted evidence, hardening, and isolated
recovery results. DigitalOcean is the authoritative environment for deployment
variables, the seven-day stability soak, and the final release status.

## Statuses

- `BLOCKED`: local prerequisites are missing or a DigitalOcean requirement fails.
- `LOCAL_READY`: local prerequisites pass and the validated branch can be deployed.
- `READY`: DigitalOcean variables and all production validation reports pass.

## Security and safety

Only deployment-variable names and presence are reported; values are never
written. The handoff is validation-only. It does not deploy, trade, connect to
Robinhood or another broker, place orders, move capital, or change strategy,
registry, allocation, governance, or cash state.

## Output

- `results/enterprise_deployment_handoff.json`
