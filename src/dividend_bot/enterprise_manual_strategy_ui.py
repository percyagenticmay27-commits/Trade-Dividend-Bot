"""Render the SWING-001 manual entry-strategy form from its declared contract.

The Enterprise host is a presentation consumer. It reads only the registered
Swing form contract and never writes Swing configuration directly.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping


def _manual_contract_path(row: Mapping[str, Any]) -> Path | None:
    root_raw = row.get("evidence_root")
    artifacts = row.get("published_artifacts")
    if not isinstance(root_raw, str) or not root_raw.strip() or not isinstance(artifacts, list):
        return None
    root = Path(root_raw).resolve(strict=False)
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        if str(artifact.get("artifact_type") or "").strip().lower() != "manual_strategy":
            continue
        raw_path = artifact.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        candidate = (root / raw_path).resolve(strict=False) if not Path(raw_path).is_absolute() else Path(raw_path).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        return candidate if candidate.suffix.lower() == ".json" else None
    return None


def load_manual_strategy_contract(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if str(row.get("strategy_id") or "").upper() != "SWING-001":
        return None
    path = _manual_contract_path(row)
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    if payload.get("strategy_id") != "SWING-001" or payload.get("paper_trade_mode") is not True:
        return None
    return payload


def _field(contract: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    fields = contract.get("fields")
    if not isinstance(fields, list):
        return {}
    for item in fields:
        if isinstance(item, Mapping) and item.get("name") == name:
            return item
    return {}


def _options(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    return "".join(
        f"<option value='{html.escape(str(value), quote=True)}'>{html.escape(str(value))}</option>"
        for value in values
    )


def _rule_row(prefix: str, operators: Any, disabled: str, *, regime: bool = False) -> str:
    source_placeholder = "Regime source" if regime else "Indicator / source"
    value_placeholder = "Value" if regime else "Value / indicator"
    return (
        "<div class='manual-rule-row'>"
        f"<input name='{prefix}_left' placeholder='{source_placeholder}' aria-label='{source_placeholder}'{disabled}>"
        f"<select name='{prefix}_operator' aria-label='Rule operator'{disabled}>{_options(operators)}</select>"
        f"<input name='{prefix}_right' placeholder='{value_placeholder}' aria-label='Rule value'{disabled}>"
        f"<input name='{prefix}_period' type='number' min='1' placeholder='Period (optional)' aria-label='Rule period'{disabled}>"
        "</div>"
    )


def render_manual_strategy_panel(row: Mapping[str, Any]) -> str:
    contract = load_manual_strategy_contract(row)
    if contract is None:
        return (
            "<section class='manual-strategy-panel'>"
            "<h3>Manual Strategy</h3>"
            "<div class='data-availability data-availability-pending'>"
            "<strong>Form contract pending</strong>"
            "<span>SWING-001 has not yet published a readable manual strategy form contract.</span>"
            "</div></section>"
        )

    registry = contract.get("current_registry") if isinstance(contract.get("current_registry"), Mapping) else {}
    strategies = registry.get("strategies") if isinstance(registry.get("strategies"), list) else []
    assignments = registry.get("assignments") if isinstance(registry.get("assignments"), list) else []
    timeframe = _field(contract, "timeframe")
    direction = _field(contract, "direction")
    entry_logic = _field(contract, "rule_logic")
    regime_logic = _field(contract, "regime_logic")
    entry_rule = _field(contract, "rules")
    regime_rule = _field(contract, "regime_filters")
    submission = contract.get("submission_contract") if isinstance(contract.get("submission_contract"), Mapping) else {}
    intake_ready = submission.get("status") == "AVAILABLE"
    disabled = "" if intake_ready else " disabled"
    save_label = "Save Strategy" if intake_ready else "Save unavailable — Swing intake pending"

    current_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('strategy_id') or ''))}</td>"
        f"<td>{html.escape(str(item.get('name') or ''))}</td>"
        f"<td>{html.escape(str(item.get('timeframe') or ''))}</td>"
        f"<td>{html.escape(str(item.get('number_of_entries') or 1))}</td>"
        "</tr>"
        for item in strategies if isinstance(item, Mapping)
    ) or "<tr><td colspan='4'>No manual strategies are registered yet.</td></tr>"
    assignment_rows = "".join(
        "<li>"
        f"<strong>{html.escape(str(item.get('underlying_symbol') or ''))}</strong> → "
        f"{html.escape(str(item.get('strategy_id') or ''))}"
        "</li>"
        for item in assignments if isinstance(item, Mapping)
    ) or "<li>No explicit underlying assignments yet.</li>"

    entry_row = _rule_row("entry_rule", entry_rule.get("operator_choices"), disabled)
    regime_row = _rule_row("regime_rule", regime_rule.get("operator_choices"), disabled, regime=True)

    return f"""
<section class='manual-strategy-panel' data-manual-strategy-form>
  <header class='manual-strategy-heading'>
    <div><h3>Manual Strategy Entry</h3><p>Define entry timing for an underlying. Swing remains the capital-allocation authority and the verified mapping remains the execution-vehicle authority.</p></div>
    <span class='paper-only-badge'>PAPER ONLY</span>
  </header>
  <div class='manual-strategy-authority'>
    <strong>Allocation:</strong> {html.escape(str(contract.get('allocation_authority') or 'SWING_PORTFOLIO_ALLOCATOR'))}
    &nbsp;·&nbsp; <strong>Assignment:</strong> UNDERLYING SYMBOL
    &nbsp;·&nbsp; <strong>Execution vehicle:</strong> VERIFIED SWING MAPPING
  </div>
  <form class='manual-strategy-form' method='post' action='/strategy/manual-entry'{disabled}>
    <div class='manual-form-grid'>
      <label><span>Strategy Name</span><input name='name' required{disabled}></label>
      <label><span>Strategy ID</span><input name='strategy_id' required placeholder='NFLX_DAILY_ENTRY_V1'{disabled}></label>
      <label><span>Underlying Symbol</span><input name='underlying_symbol' required placeholder='NFLX'{disabled}></label>
      <label><span>Execution Vehicle</span><input value='Resolved from verified mapping' readonly></label>
      <label><span>Direction</span><select name='direction'{disabled}>{_options(direction.get('choices'))}</select></label>
      <label><span>Timeframe</span><select name='timeframe'{disabled}>{_options(timeframe.get('choices'))}</select></label>
      <label><span>Session</span><input name='session' value='REGULAR_SESSION'{disabled}></label>
      <label><span>Number of Entries</span><input name='number_of_entries' type='number' min='1' value='1' required{disabled}></label>
    </div>
    <fieldset><legend>Entry Rules</legend>
      <div class='manual-inline-choice'><label>Combine rules with <select name='rule_logic'{disabled}>{_options(entry_logic.get('choices'))}</select></label></div>
      <div class='manual-rule-list' data-entry-rule-list>{entry_row}</div>
      <button type='button' class='secondary-action' data-add-manual-rule='entry'{disabled}>+ Add Entry Rule</button>
      <p class='form-help'>For a BETWEEN rule, enter the value as minimum,maximum (example: 45,65).</p>
    </fieldset>
    <fieldset><legend>Confirmation</legend><input name='confirmation' placeholder='Example: 2 consecutive qualifying Daily closes'{disabled}></fieldset>
    <fieldset><legend>Regime Filters</legend>
      <div class='manual-inline-choice'><label>Combine filters with <select name='regime_logic'{disabled}>{_options(regime_logic.get('choices'))}</select></label></div>
      <div class='manual-rule-list' data-regime-rule-list>{regime_row}</div>
      <button type='button' class='secondary-action' data-add-manual-rule='regime'{disabled}>+ Add Regime Filter</button>
      <p class='form-help'>Multiple filters are submitted and stored as structured rules, not as one comma-delimited string.</p>
    </fieldset>
    <div class='manual-form-grid'>
      <label><span>Exit Policy</span><input name='exit_policy_id' placeholder='Existing Swing exit policy'{disabled}></label>
      <label><span>Re-entry Cooldown / Reset</span><input name='reentry_cooldown' placeholder='Optional'{disabled}></label>
      <label><span>Allocation Authority</span><input value='SWING_PORTFOLIO_ALLOCATOR' readonly></label>
      <label><span>Paper Trade Mode</span><input value='TRUE' readonly></label>
    </div>
    <div class='manual-form-actions'><button type='submit' class='primary-action'{disabled}>{html.escape(save_label)}</button></div>
  </form>
  <details class='manual-current-strategies'><summary>Current manual strategies and assignments</summary>
    <table><thead><tr><th>ID</th><th>Name</th><th>Timeframe</th><th>Entries</th></tr></thead><tbody>{current_rows}</tbody></table>
    <h4>Underlying assignments</h4><ul>{assignment_rows}</ul>
  </details>
  <script>
  (() => {{
    const root = document.currentScript && document.currentScript.closest('[data-manual-strategy-form]');
    if (!root) return;
    root.querySelectorAll('[data-add-manual-rule]').forEach((button) => {{
      button.addEventListener('click', () => {{
        const kind = button.getAttribute('data-add-manual-rule');
        const list = root.querySelector(kind === 'entry' ? '[data-entry-rule-list]' : '[data-regime-rule-list]');
        if (!list || !list.firstElementChild) return;
        const clone = list.firstElementChild.cloneNode(true);
        clone.querySelectorAll('input').forEach((input) => input.value = '');
        clone.querySelectorAll('select').forEach((select) => select.selectedIndex = 0);
        list.appendChild(clone);
      }});
    }});
  }})();
  </script>
</section>
"""


def manual_strategy_ui_css() -> str:
    return """
<style>
.manual-strategy-heading{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.manual-strategy-heading h3{margin-bottom:4px}.paper-only-badge{padding:6px 10px;border-radius:999px;background:#ede9fe;color:#5b21b6;font-weight:900;font-size:12px;white-space:nowrap}.manual-strategy-authority{margin:14px 0;padding:12px 14px;border-radius:10px;background:#eef6ff;border:1px solid #bfdbfe;color:#1e3a8a}.manual-strategy-form{display:grid;gap:16px}.manual-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.manual-strategy-form label{display:grid;gap:6px}.manual-strategy-form label>span,.manual-strategy-form legend{font-weight:800;color:#344054}.manual-strategy-form input,.manual-strategy-form select{width:100%;box-sizing:border-box;padding:10px 11px;border:1px solid #cbd5e1;border-radius:9px;background:#fff}.manual-strategy-form input[readonly]{background:#f1f5f9;color:#475569}.manual-strategy-form fieldset{border:1px solid #dbe3ef;border-radius:12px;padding:14px}.manual-rule-list{display:grid;gap:8px;margin:10px 0}.manual-rule-row{display:grid;grid-template-columns:1.15fr .65fr 1.15fr .8fr;gap:8px}.secondary-action,.primary-action{padding:9px 13px;border-radius:9px;font-weight:800}.secondary-action{border:1px solid #8b5cf6;background:#fff;color:#5d18d6}.primary-action{border:0;background:#5d18d6;color:#fff}.primary-action:disabled,.secondary-action:disabled{opacity:.55;cursor:not-allowed}.form-help{font-size:12px;color:#64748b}.manual-current-strategies{margin-top:18px}.manual-current-strategies table{width:100%;border-collapse:collapse}.manual-current-strategies th,.manual-current-strategies td{padding:9px;border-bottom:1px solid #e5e7eb;text-align:left}.workspace-tab[data-workspace-tab-target='manual-strategy'].active{background:#0f766e}
@media(max-width:700px){.manual-form-grid,.manual-rule-row{grid-template-columns:1fr}.manual-strategy-heading{display:block}.paper-only-badge{display:inline-block;margin-top:8px}}
</style>"""
