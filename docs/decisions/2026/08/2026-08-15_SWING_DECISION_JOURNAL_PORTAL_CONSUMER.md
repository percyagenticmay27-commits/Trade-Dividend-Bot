# Decision: SWING-001 Decision Journal portal consumer

Date: 2026-08-15  
Repository: Trade-Dividend-Bot  
Branch: feature/dashboard-refresh-discovery-summary

## Decision

Enterprise AI CIO consumes the frozen SWING-001 Decision Journal through Registry v2. The registered standalone `swing_decision_journal_report` is authoritative and takes precedence over the embedded `dashboard_sections.decisions` compatibility view.

Artifact paths remain relative to the external registration's `repository_root` and must remain contained beneath that root.

## Presentation boundary

SWING-001 uses stock lifecycle cards, not the Dividend pair lifecycle:

- **Open Position Decisions** displays authentic open-position decisions.
- **Candidate Decisions** displays committee-owned candidate decisions.
- Each card displays symbol, decision scope, current state, current decision, current owner, rationale, alternatives, evidence timestamp, and committee evidence timeline.
- Evidence warnings display separately as **Evidence Disclosures**.
- Empty authoritative evidence displays the producer's no-decisions message.
- Dividend pair, income-leg, and leverage-leg terminology remains exclusive to DIVIDEND-001.

## Prohibited inference

The host never treats `rebalance_actions.json` calculations as executed decisions. It does not fabricate BUY, SELL, sale, exit, closure, or closed-position evidence. Reports containing a decision outside the registered advisory contract fail closed.

## Governance

SWING-001 remains allocated $4,500. The consumer is paper-only, advisory-only, and read-only. It introduces no live trading, broker execution, order placement, capital movement, or Robinhood execution.

Trade-Swing-Bot is frozen at handoff commit `d83e0dc` and was not modified.

## Validation

```bash
python -m py_compile \
  src/dividend_bot/enterprise_strategy_kpi_adapter.py \
  src/dividend_bot/enterprise_swing_decision_journal_ui.py \
  src/dividend_bot/enterprise_portal_strategy_ui_v2.py

pytest \
  tests/test_enterprise_swing_decision_journal_ui.py \
  tests/test_enterprise_portal_swing_decisions_integration.py \
  tests/test_enterprise_strategy_kpi_adapter.py \
  tests/test_strategy_decision_journal_renderer.py \
  tests/test_portal_dashboard_routes.py \
  -v
```

After tests pass, refresh the Enterprise Registry and dashboards, restart only `dividend-allocation.service`, and validate the SWING-001 Decisions deep link.
