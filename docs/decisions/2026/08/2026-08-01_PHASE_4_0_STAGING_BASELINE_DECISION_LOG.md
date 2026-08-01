# Phase 4.0 DigitalOcean Staging Baseline Decision Log

## Decision ID

DEC-2026-08-01-PHASE-4-0

## Status

Approved and implemented.

## Decision

Phase 4 UI work will be deployed incrementally to DigitalOcean after local tests pass. The existing allocation page must remain intact while a separate read-only preview is validated.

## Approved staging boundary

- Generate `results/enterprise-preview.html` from the same Executive and Investor dashboard JSON artifacts used by the Enterprise portal.
- Generate `results/enterprise-preview-status.json` for deployment validation.
- Recommended preview route: `/enterprise-preview`.
- The preview must display a visible staging banner.
- The preview must remain paper-only, reporting-only, read-only, with broker execution and capital movement disabled.
- Do not replace the current root allocation page during Phase 4 development.

## Implementation

- `generate_enterprise_preview.py`
- `tests/test_generate_enterprise_preview.py`
- Existing renderer: `src/dividend_bot/portal_dashboard_routes.py`

## Local development order

1. Run the consolidated Enterprise portal refresh.
2. Generate the standalone preview.
3. Run focused tests.
4. Commit and push.
5. Pull on DigitalOcean.
6. Regenerate the portal and preview.
7. Expose the preview under a separate route.
8. Capture a screenshot and compare it with the approved UI specifications.

## Required artifacts

- `results/ai_cio_executive_dashboard.json`
- `results/enterprise_investor_dashboard.json`
- `results/enterprise_dashboard_intelligence.json`
- `results/enterprise-preview.html`
- `results/enterprise-preview-status.json`

## DigitalOcean acceptance checks

- Preview route loads without modifying the existing allocation page.
- Staging banner is visible.
- Executive and Investor views can be selected.
- Strategy IDs match the Registry discovery output.
- Both dashboard artifacts contain Enterprise intelligence.
- Missing evidence is shown as unavailable or not reported rather than invented.
- No live trading, broker execution, or capital movement path is introduced.

## Deployment evidence

Store screenshots under:

`docs/decisions/2026/08/images/`

Recommended filename:

`2026-08-01_enterprise_preview_digitalocean.png`
