"""Render the DIVIDEND-001 manual shadow-strategy form."""
from __future__ import annotations

import html

from .dividend_manual_strategy_evaluator import SUPPORTED_OPERATORS
from .dividend_manual_strategy_intake import SUPPORTED_OPERANDS


def _options(values) -> str:
    return "".join(
        f"<option value='{html.escape(str(value), quote=True)}'>"
        f"{html.escape(str(value))}</option>"
        for value in sorted(values)
    )


def _rule_row(prefix: str) -> str:
    operands = _options(SUPPORTED_OPERANDS)
    operators = _options(SUPPORTED_OPERATORS)

    return (
        f"<div class='dividend-manual-rule-row' "
        f"data-dividend-manual-rule-row='{prefix}'>"
        f"<select name='{prefix}_left' required>"
        f"<option value=''>Source</option>{operands}</select>"
        f"<select name='{prefix}_operator' required>"
        f"<option value=''>Operator</option>{operators}</select>"
        f"<input name='{prefix}_right' "
        f"placeholder='Indicator or numeric value' required>"
        f"<button type='button' class='remove-rule-action' "
        f"data-remove-dividend-rule='{prefix}'>Remove</button>"
        "</div>"
    )


def _rule_section(
    title: str,
    prefix: str,
    logic_name: str,
    *,
    required: bool,
) -> str:
    row = _rule_row(prefix)
    required_text = "At least one entry rule is required." if required else (
        "Exit rules are optional; without them the shadow strategy "
        "will remain in-market until a supported exit rule is added."
    )

    return f"""
<fieldset>
  <legend>{html.escape(title)}</legend>
  <p class='section-help'>{html.escape(required_text)}</p>
  <label class='dividend-manual-logic'>
    <span>Combine rules with</span>
    <select name='{logic_name}'>
      <option value='AND'>AND</option>
      <option value='OR'>OR</option>
    </select>
  </label>
  <div class='dividend-manual-rule-list' data-dividend-rule-list='{prefix}'>
    {row}
  </div>
  <button type='button'
          class='secondary-action'
          data-add-dividend-rule='{prefix}'>
    + Add Rule
  </button>
</fieldset>
"""


def render_dividend_manual_strategy_panel() -> str:
    entry = _rule_section(
        "Entry Rules",
        "entry_rule",
        "entry_logic",
        required=True,
    )

    exit_rules = _rule_section(
        "Exit Rules",
        "exit_rule",
        "exit_logic",
        required=False,
    )

    operands = html.escape(
        ", ".join(sorted(SUPPORTED_OPERANDS))
    )

    template = """
<section class='dividend-manual-strategy-panel'
         data-dividend-manual-strategy-form>

  <header class='manual-strategy-heading'>
    <div>
      <h3>Dividend Manual Strategy</h3>
      <p>
        Create a pair-scoped research challenger without changing
        the current Primary strategy.
      </p>
    </div>
    <span class='paper-only-badge'>PAPER / SHADOW ONLY</span>
  </header>

  <div class='manual-strategy-authority'>
    <strong>Research Role:</strong> TEST_CANDIDATE
    &nbsp;·&nbsp;
    <strong>Execution:</strong> NONE
    &nbsp;·&nbsp;
    <strong>Capital Movement:</strong> NONE
    &nbsp;·&nbsp;
    <strong>Automatic Promotion:</strong> DISABLED
  </div>

  <div class='manual-strategy-guide'>
    <strong>Current supported evidence:</strong>
    __OPERANDS__.
    Numeric constants may also be entered on the right side of a rule.
  </div>

  <form class='manual-strategy-form'
        method='post'
        action='/strategy/dividend-manual-entry'>

    <div class='manual-form-grid'>
      <label>
        <span>Strategy Name</span>
        <input name='display_name'
               required
               placeholder='Strategy C'>
      </label>

      <label>
        <span>Strategy ID</span>
        <input name='strategy_id'
               required
               placeholder='STRATEGY_C'>
        <small class='field-help'>
          STRATEGY_A and STRATEGY_B are protected built-ins.
        </small>
      </label>

      <label>
        <span>Dividend Pair</span>
        <input name='pair'
               required
               placeholder='AMDW / AMDL'>
      </label>

      <label>
        <span>Research Assignment</span>
        <input value='SHADOW / TEST_CANDIDATE' readonly>
      </label>

      <label class='manual-description-field'>
        <span>Description</span>
        <input name='description'
               placeholder='Research challenger for this pair'>
      </label>

      <label>
        <span>Paper Trade Mode</span>
        <input value='TRUE' readonly>
      </label>
    </div>

    __ENTRY_RULES__
    __EXIT_RULES__

    <div class='manual-form-actions'>
      <button type='submit' class='primary-action'>
        Save Shadow Strategy
      </button>
    </div>
  </form>

  <script>
  (() => {
    const root =
      document.currentScript &&
      document.currentScript.closest(
        '[data-dividend-manual-strategy-form]'
      );

    if (!root) return;

    const templates = {};

    root.querySelectorAll(
      '[data-dividend-rule-list]'
    ).forEach((list) => {
      const key =
        list.getAttribute('data-dividend-rule-list');

      if (key && list.firstElementChild) {
        templates[key] =
          list.firstElementChild.cloneNode(true);
      }
    });

    const reset = (row) => {
      row.querySelectorAll('input').forEach(
        (input) => input.value = ''
      );

      row.querySelectorAll('select').forEach(
        (select) => select.selectedIndex = 0
      );

      return row;
    };

    const updateButtons = () => {
      root.querySelectorAll(
        '[data-dividend-rule-list]'
      ).forEach((list) => {
        const key =
          list.getAttribute('data-dividend-rule-list');

        list.querySelectorAll(
          '[data-remove-dividend-rule]'
        ).forEach((button) => {
          button.disabled =
            key === 'entry_rule' &&
            list.children.length <= 1;
        });
      });
    };

    root.querySelectorAll(
      '[data-add-dividend-rule]'
    ).forEach((button) => {
      button.addEventListener('click', () => {
        const key =
          button.getAttribute(
            'data-add-dividend-rule'
          );

        const list =
          root.querySelector(
            "[data-dividend-rule-list='" + key + "']"
          );

        const template = key
          ? templates[key]
          : null;

        if (!list || !template) return;

        list.appendChild(
          reset(template.cloneNode(true))
        );

        updateButtons();
      });
    });

    root.addEventListener('click', (event) => {
      const target = event.target;

      if (!(target instanceof Element)) return;

      const button =
        target.closest(
          '[data-remove-dividend-rule]'
        );

      if (!button || !root.contains(button)) {
        return;
      }

      const key =
        button.getAttribute(
          'data-remove-dividend-rule'
        );

      const list = key
        ? root.querySelector(
            "[data-dividend-rule-list='" + key + "']"
          )
        : null;

      const row =
        button.closest(
          '[data-dividend-manual-rule-row]'
        );

      if (!list || !row) return;

      if (
        key === 'entry_rule' &&
        list.children.length <= 1
      ) {
        return;
      }

      row.remove();
      updateButtons();
    });

    updateButtons();
  })();
  </script>
</section>
"""

    return (
        template
        .replace("__OPERANDS__", operands)
        .replace("__ENTRY_RULES__", entry)
        .replace("__EXIT_RULES__", exit_rules)
    )


def dividend_manual_strategy_ui_css() -> str:
    return """
<style>
.dividend-manual-strategy-panel{
  display:grid;
  gap:16px;
}

.dividend-manual-rule-list{
  display:grid;
  gap:8px;
  margin:10px 0;
}

.dividend-manual-rule-row{
  display:grid;
  grid-template-columns:1fr .8fr 1fr auto;
  gap:8px;
  align-items:center;
}

.dividend-manual-logic{
  max-width:260px;
  margin-bottom:8px;
}

.manual-description-field{
  grid-column:1 / -1;
}

.workspace-tab[
  data-workspace-tab-target='manual-strategy'
].active{
  background:#0f766e;
}

@media(max-width:760px){
  .dividend-manual-rule-row{
    grid-template-columns:1fr;
  }
}
</style>
"""
