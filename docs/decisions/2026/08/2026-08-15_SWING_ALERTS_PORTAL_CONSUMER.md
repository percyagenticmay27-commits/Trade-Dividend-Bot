# Decision: SWING-001 authoritative Alerts portal consumer

Date: 2026-08-15  
Repository: Trade-Dividend-Bot  
Branch: feature/dashboard-refresh-discovery-summary

## Decision

Enterprise AI CIO consumes SWING-001 Alerts through Registry v2. The dedicated registered `swing_strategy_alerts_report` is authoritative. Its path is resolved relative to the external strategy's registered `repository_root` and must remain contained by that root.

The registered KPI `dashboard_sections.alerts` payload is a compatibility fallback only when the dedicated report is unavailable. Host-owned internal Swing fallback evidence is considered only when external registered evidence is genuinely unavailable.

## Rendering contract

- Preserve the published `CURRENT_AUTHORITATIVE_EVIDENCE_ONLY` classifications.
- Render actionable `alerts` without recalculation or reinterpretation.
- Render `evidence_warnings` separately as **Evidence Disclosures**.
- For an authoritative empty alert set, show: “Current authoritative Swing evidence was evaluated and no actionable alerts were found.”
- Never revive rejected legacy dashboard flags as current alerts.
- Missing or unsafe evidence remains unavailable; no all-clear is fabricated.
- Preserve HTML escaping and severity/priority presentation classes.
- DIVIDEND-001 continues through its existing Alerts renderer unchanged.

## Governance

SWING-001 remains allocated $4,500 and DIVIDEND-001 remains allocated $5,000. All views are paper-only, advisory-only, and read-only. No live trading, broker execution, order placement, capital movement, or Robinhood execution is introduced.

## Validation and deployment

Run:

```bash
python -m py_compile \
  src/dividend_bot/enterprise_strategy_kpi_adapter.py \
  src/dividend_bot/enterprise_swing_alerts_ui.py \
  src/dividend_bot/enterprise_portal_strategy_ui_v2.py

pytest \
  tests/test_enterprise_swing_alerts_ui.py \
  tests/test_enterprise_strategy_kpi_adapter.py \
  tests/test_enterprise_portal_swing_alerts_integration.py \
  tests/test_portal_dashboard_routes.py \
  -v
```

After tests pass, refresh the Enterprise Registry and dashboards, restart `dividend-allocation.service`, and inspect `/executive-dashboard?strategy=SWING-001&tab=alerts`.

Trade-Swing-Bot is a frozen producer for this change and must not be modified.
