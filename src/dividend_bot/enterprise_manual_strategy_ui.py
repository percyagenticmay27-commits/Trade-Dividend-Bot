"""Render the SWING-001 manual trading-strategy form from its declared contract."""
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
        if not isinstance(artifact, Mapping) or str(artifact.get("artifact_type") or "").lower() != "manual_strategy":
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
    if not isinstance(payload, Mapping) or payload.get("strategy_id") != "SWING-001" or payload.get("paper_trade_mode") is not True:
        return None
    return payload


def _field(contract: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    fields = contract.get("fields")
    if isinstance(fields, list):
        for item in fields:
            if isinstance(item, Mapping) and item.get("name") == name:
                return item
    return {}


def _options(values: Any, selected: str | None = None, *, blank: bool = False) -> str:
    output = "<option value=''></option>" if blank else ""
    if not isinstance(values, list):
        return output
    for value in values:
        text = str(value)
        sel = " selected" if selected is not None and text == selected else ""
        output += f"<option value='{html.escape(text, quote=True)}'{sel}>{html.escape(text)}</option>"
    return output


def _help(contract: Mapping[str, Any], name: str) -> str:
    field = _field(contract, name)
    help_text = str(field.get("help") or "").strip()
    example = str(field.get("example") or "").strip()
    parts: list[str] = []
    if help_text:
        parts.append(html.escape(help_text))
    if example:
        parts.append(f"<strong>Example:</strong> {html.escape(example)}")
    return f"<small class='field-help'>{' '.join(parts)}</small>" if parts else ""


def _rule_row(prefix: str, field: Mapping[str, Any], disabled: str, *, kind: str = "entry") -> str:
    source_placeholder = "CHOP / close / etc." if kind == "regime" else "close / indicator"
    return (
        f"<div class='manual-rule-row' data-manual-rule-row='{prefix}'>"
        f"<input name='{prefix}_left' placeholder='{source_placeholder}' aria-label='Rule source'{disabled}>"
        f"<select name='{prefix}_operator' aria-label='Rule operator'{disabled}>{_options(field.get('operator_choices'))}</select>"
        f"<input name='{prefix}_right' placeholder='Value / indicator' aria-label='Rule value'{disabled}>"
        f"<input name='{prefix}_period' type='number' min='1' placeholder='Period' aria-label='Rule period'{disabled}>"
        f"<input name='{prefix}_factor' type='number' min='0' step='0.01' placeholder='Factor' aria-label='Rule factor'{disabled}>"
        f"<select name='{prefix}_smoothing' aria-label='Rule smoothing'{disabled}>{_options(field.get('smoothing_choices'), blank=True)}</select>"
        f"<select name='{prefix}_price_source' aria-label='Rule price source'{disabled}>{_options(field.get('price_source_choices'), blank=True)}</select>"
        f"<button type='button' class='remove-rule-action' data-remove-manual-rule='{prefix}' aria-label='Remove rule'{disabled}>Remove</button>"
        "</div>"
    )


def _rule_section(title: str, contract: Mapping[str, Any], field_name: str, prefix: str, disabled: str, *, logic_name: str | None = None, add_label: str = "+ Add Rule", kind: str = "entry") -> str:
    field = _field(contract, field_name)
    logic = _field(contract, logic_name) if logic_name else {}
    logic_html = ""
    if logic_name:
        logic_html = (
            f"<div class='manual-inline-choice'><label>Combine with "
            f"<select name='{logic_name}'{disabled}>{_options(logic.get('choices'))}</select>"
            f"{_help(contract, logic_name)}</label></div>"
        )
    row = _rule_row(prefix, field, disabled, kind=kind)
    return f"""
    <fieldset><legend>{html.escape(title)}</legend>
      <div class='section-help'>{_help(contract, field_name)}</div>
      {logic_html}
      <div class='manual-rule-column-labels'><span>Source</span><span>Operator</span><span>Value / Indicator</span><span>Period</span><span>Factor</span><span>Smoothing</span><span>Price Source</span><span>Action</span></div>
      <div class='manual-rule-list' data-rule-list='{prefix}'>{row}</div>
      <button type='button' class='secondary-action' data-add-manual-rule='{prefix}'{disabled}>{html.escape(add_label)}</button>
    </fieldset>
    """


def render_manual_strategy_panel(row: Mapping[str, Any]) -> str:
    contract = load_manual_strategy_contract(row)
    if contract is None:
        return "<section class='manual-strategy-panel'><h3>Manual Strategy</h3><div class='data-availability data-availability-pending'><strong>Form contract pending</strong><span>SWING-001 has not yet published a readable manual strategy form contract.</span></div></section>"

    registry = contract.get("current_registry") if isinstance(contract.get("current_registry"), Mapping) else {}
    strategies = registry.get("strategies") if isinstance(registry.get("strategies"), list) else []
    assignments = registry.get("assignments") if isinstance(registry.get("assignments"), list) else []
    submission = contract.get("submission_contract") if isinstance(contract.get("submission_contract"), Mapping) else {}
    intake_ready = submission.get("status") == "AVAILABLE"
    disabled = "" if intake_ready else " disabled"
    save_label = "Save Strategy" if intake_ready else "Save unavailable — Swing intake pending"

    assignment_mode = _field(contract, "assignment_mode")
    timeframe = _field(contract, "timeframe")
    direction = _field(contract, "direction")
    cooldown_unit = _field(contract, "conditional_exit_cooldown_unit")

    current_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('strategy_id') or ''))}</td>"
        f"<td>{html.escape(str(item.get('name') or ''))}</td>"
        f"<td>{html.escape(str(item.get('timeframe') or ''))}</td>"
        f"<td>{html.escape(str(item.get('number_of_entries') or 1))}</td>"
        f"<td>{html.escape(str(item.get('confirmation_bars') or 1))}</td>"
        "</tr>" for item in strategies if isinstance(item, Mapping)
    ) or "<tr><td colspan='5'>No manual strategies are registered yet.</td></tr>"
    assignment_rows = "".join(
        "<li>"
        f"<strong>{html.escape(str(item.get('underlying_symbol') or ''))}</strong> → "
        f"{html.escape(str(item.get('strategy_id') or ''))} "
        f"<em>({html.escape(str(item.get('assignment_mode') or 'DIRECT'))})</em></li>"
        for item in assignments if isinstance(item, Mapping)
    ) or "<li>No explicit underlying assignments yet.</li>"

    entry_section = _rule_section("Entry Rules", contract, "rules", "entry_rule", disabled, logic_name="rule_logic", add_label="+ Add Entry Rule")
    regime_section = _rule_section("Regime Filters", contract, "regime_filters", "regime_rule", disabled, logic_name="regime_logic", add_label="+ Add Regime Filter", kind="regime")
    normal_exit_section = _rule_section("Normal Exit Rules (always active)", contract, "normal_exit_rules", "normal_exit_rule", disabled, logic_name="normal_exit_logic", add_label="+ Add Normal Exit Rule")
    conditional_exit_section = _rule_section("Conditional Exit Rules", contract, "conditional_exit_rules", "conditional_exit_rule", disabled, add_label="+ Add Conditional Exit Rule")

    return f"""
<section class='manual-strategy-panel' data-manual-strategy-form>
  <header class='manual-strategy-heading'>
    <div><h3>Manual Trading Strategy</h3><p>Define entry, regime, exit, and cooldown behavior for an underlying without changing Swing's allocation authority.</p></div>
    <span class='paper-only-badge'>PAPER ONLY</span>
  </header>
  <div class='manual-strategy-authority'><strong>Allocation:</strong> SWING_PORTFOLIO_ALLOCATOR &nbsp;·&nbsp; <strong>Assignment:</strong> DIRECT or SHADOW &nbsp;·&nbsp; <strong>Execution:</strong> VERIFIED SWING MAPPING</div>
  <div class='manual-strategy-guide'><strong>Frozen-strategy friendly:</strong> Indicator parameters are explicit. For Keltner, enter period, factor, smoothing, and price source. Confirmation counts completed bars. Exit rules are separate from entry rules.</div>
  <form class='manual-strategy-form' method='post' action='/strategy/manual-entry'{disabled}>
    <div class='manual-form-grid'>
      <label><span>Strategy Name</span><input name='name' required{disabled}>{_help(contract, 'name')}</label>
      <label><span>Strategy ID</span><input name='strategy_id' required placeholder='M_HMA50_DAILY'{disabled}>{_help(contract, 'strategy_id')}</label>
      <label><span>Underlying Symbol</span><input name='underlying_symbol' required placeholder='NFLX'{disabled}>{_help(contract, 'underlying_symbol')}</label>
      <label><span>Assignment Mode</span><select name='assignment_mode' required{disabled}>{_options(assignment_mode.get('choices'))}</select>{_help(contract, 'assignment_mode')}</label>
      <label><span>Execution Vehicle</span><input value='Resolved from verified mapping' readonly>{_help(contract, 'execution_symbol')}</label>
      <label><span>Direction</span><select name='direction'{disabled}>{_options(direction.get('choices'))}</select>{_help(contract, 'direction')}</label>
      <label><span>Timeframe</span><select name='timeframe'{disabled}>{_options(timeframe.get('choices'))}</select>{_help(contract, 'timeframe')}</label>
      <label><span>Session</span><input name='session' value='REGULAR_SESSION'{disabled}>{_help(contract, 'session')}</label>
      <label><span>Number of Entries</span><input name='number_of_entries' type='number' min='1' value='1' required{disabled}>{_help(contract, 'number_of_entries')}</label>
      <label><span>Consecutive Qualifying Bars</span><input name='confirmation_bars' type='number' min='1' value='1' required{disabled}>{_help(contract, 'confirmation_bars')}</label>
    </div>
    {entry_section}
    {regime_section}
    {normal_exit_section}
    <fieldset><legend>Conditional / Profit-Activated Exit</legend>
      <label class='check-row'><input name='conditional_exit_enabled' type='checkbox' value='true'{disabled}><span>Enable conditional exit branch</span></label>
      {_help(contract, 'conditional_exit_enabled')}
      <div class='manual-form-grid'>
        <label><span>Activate when Position P/L &gt; $</span><input name='conditional_exit_pl_threshold' type='number' step='0.01' value='0'{disabled}>{_help(contract, 'conditional_exit_pl_threshold')}</label>
        <label><span>Cooldown After Conditional Exit</span><input name='conditional_exit_cooldown_bars' type='number' min='0' value='0'{disabled}>{_help(contract, 'conditional_exit_cooldown_bars')}</label>
        <label><span>Cooldown Unit</span><select name='conditional_exit_cooldown_unit'{disabled}>{_options(cooldown_unit.get('choices'))}</select>{_help(contract, 'conditional_exit_cooldown_unit')}</label>
      </div>
      {conditional_exit_section}
    </fieldset>
    <div class='manual-form-grid'>
      <label><span>Existing Exit Policy Reference</span><input name='exit_policy_id' placeholder='Optional'{disabled}>{_help(contract, 'exit_policy_id')}</label>
      <label><span>Allocation Authority</span><input value='SWING_PORTFOLIO_ALLOCATOR' readonly>{_help(contract, 'allocation_authority')}</label>
      <label><span>Paper Trade Mode</span><input value='TRUE' readonly>{_help(contract, 'paper_trade_mode')}</label>
    </div>
    <div class='manual-form-actions'><button type='submit' class='primary-action'{disabled}>{html.escape(save_label)}</button></div>
  </form>
  <details class='manual-current-strategies'><summary>Current manual strategies and assignments</summary>
    <table><thead><tr><th>ID</th><th>Name</th><th>Timeframe</th><th>Entries</th><th>Confirm Bars</th></tr></thead><tbody>{current_rows}</tbody></table>
    <h4>Underlying assignments</h4><ul>{assignment_rows}</ul>
  </details>
  <script>
  (() => {{
    const root = document.currentScript && document.currentScript.closest('[data-manual-strategy-form]');
    if (!root) return;

    const templates = {{}};
    root.querySelectorAll('[data-rule-list]').forEach((list) => {{
      const key = list.getAttribute('data-rule-list');
      if (key && list.firstElementChild) templates[key] = list.firstElementChild.cloneNode(true);
    }});

    const resetRow = (row) => {{
      row.querySelectorAll('input').forEach((input) => input.value = '');
      row.querySelectorAll('select').forEach((select) => select.selectedIndex = 0);
      return row;
    }};

    const updateRemoveButtons = () => {{
      root.querySelectorAll('[data-rule-list]').forEach((list) => {{
        const key = list.getAttribute('data-rule-list');
        const buttons = list.querySelectorAll('[data-remove-manual-rule]');
        buttons.forEach((button) => {{
          button.disabled = key === 'entry_rule' && list.children.length <= 1;
          button.title = button.disabled ? 'At least one Entry Rule is required' : 'Remove this rule';
        }});
      }});
    }};

    root.querySelectorAll('[data-add-manual-rule]').forEach((button) => {{
      button.addEventListener('click', () => {{
        const key = button.getAttribute('data-add-manual-rule');
        const list = root.querySelector(`[data-rule-list='${{key}}']`);
        const template = key ? templates[key] : null;
        if (!list || !template) return;
        list.appendChild(resetRow(template.cloneNode(true)));
        updateRemoveButtons();
      }});
    }});

    root.addEventListener('click', (event) => {{
      const target = event.target;
      if (!(target instanceof Element)) return;
      const button = target.closest('[data-remove-manual-rule]');
      if (!button || !root.contains(button)) return;
      const key = button.getAttribute('data-remove-manual-rule');
      const list = key ? root.querySelector(`[data-rule-list='${{key}}']`) : null;
      const row = button.closest('[data-manual-rule-row]');
      if (!list || !row) return;
      if (key === 'entry_rule' && list.children.length <= 1) return;
      row.remove();
      updateRemoveButtons();
    }});

    updateRemoveButtons();
  }})();
  </script>
</section>
"""


def manual_strategy_ui_css() -> str:
    return """
<style>
.manual-strategy-heading{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.manual-strategy-heading h3{margin-bottom:4px}.paper-only-badge{padding:6px 10px;border-radius:999px;background:#ede9fe;color:#5b21b6;font-weight:900;font-size:12px;white-space:nowrap}.manual-strategy-authority{margin:14px 0;padding:12px 14px;border-radius:10px;background:#eef6ff;border:1px solid #bfdbfe;color:#1e3a8a}.manual-strategy-guide{margin:0 0 16px;padding:12px 14px;border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0;color:#475569}.manual-strategy-form{display:grid;gap:16px}.manual-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.manual-strategy-form label{display:grid;gap:6px;align-content:start}.manual-strategy-form label>span,.manual-strategy-form legend{font-weight:800;color:#344054}.manual-strategy-form input,.manual-strategy-form select{width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid #cbd5e1;border-radius:9px;background:#fff}.manual-strategy-form input[readonly]{background:#f1f5f9;color:#475569}.manual-strategy-form fieldset{border:1px solid #dbe3ef;border-radius:12px;padding:14px}.field-help{font-size:12px;line-height:1.4;color:#64748b}.field-help strong{color:#475569}.section-help{margin:2px 0 12px}.manual-rule-list{display:grid;gap:8px;margin:8px 0 10px}.manual-rule-row,.manual-rule-column-labels{display:grid;grid-template-columns:1.05fr .6fr 1.05fr .6fr .55fr .8fr .95fr .65fr;gap:7px;align-items:center}.manual-rule-column-labels{font-size:10px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.03em}.secondary-action,.primary-action,.remove-rule-action{padding:9px 13px;border-radius:9px;font-weight:800}.secondary-action{border:1px solid #8b5cf6;background:#fff;color:#5d18d6}.primary-action{border:0;background:#5d18d6;color:#fff}.remove-rule-action{border:1px solid #dc2626;background:#fff;color:#b91c1c;padding:8px 9px}.remove-rule-action:disabled{border-color:#cbd5e1;color:#94a3b8;background:#f8fafc;cursor:not-allowed}.check-row{display:flex!important;grid-template-columns:auto 1fr!important;align-items:center;gap:8px}.check-row input{width:auto}.form-help{font-size:12px;color:#64748b}.manual-current-strategies{margin-top:18px}.manual-current-strategies table{width:100%;border-collapse:collapse}.manual-current-strategies th,.manual-current-strategies td{padding:9px;border-bottom:1px solid #e5e7eb;text-align:left}.workspace-tab[data-workspace-tab-target='manual-strategy'].active{background:#0f766e}
@media(max-width:1050px){.manual-rule-row,.manual-rule-column-labels{grid-template-columns:1fr 1fr}.manual-rule-column-labels{display:none}}
@media(max-width:700px){.manual-form-grid,.manual-rule-row{grid-template-columns:1fr}.manual-strategy-heading{display:block}.paper-only-badge{display:inline-block;margin-top:8px}}
</style>"""