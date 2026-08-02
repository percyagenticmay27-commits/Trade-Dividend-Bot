# Phase 4 Strategy Decision Journal Decision Log — 2026-08-01

## Decision ID

`DEC-2026-08-01-P4-DJ-001`

## Status

Approved, documented, and contract implementation committed. Local focused tests pending user execution.

## Accepted Decisions

### 1. Strategy-Scoped Journal

The Decision Journal tab belongs to the selected strategy KPI workspace and displays only that strategy's decisions and committee evidence.

- Swing KPI shows Swing decisions only.
- Dividend KPI shows Dividend decisions only.
- No detailed enterprise-mixed journal is permitted inside a strategy KPI.

### 2. Newest First

Decision entries are ordered by decision timestamp descending so the latest activity is immediately visible.

### 3. Dividend Uses Ecosystem Pair Decisions

The normal Dividend decision object is an ecosystem pair:

- income ETF leg;
- leverage ETF leg;
- role-specific alternatives;
- evidence explaining why each selected product beat the alternatives in the same role;
- evidence explaining why the selected pair works together.

The underlying company is context and cannot explain by itself why NVDY was selected instead of NVDW or why NVDX was selected instead of NVDU.

### 4. Explicit Self-Funded Exception

A one-instrument Dividend ecosystem is permitted only when the strategy explicitly declares self-funded mode and provides an evidence-backed reason.

### 5. Swing Uses Individual Opportunities

Swing decisions remain individual symbol/opportunity decisions and contain only Swing committee evidence, ranking, Opportunity Quality, Entry / Timing evidence, alternatives, and final Swing rationale.

### 6. Decision Journal Images

Each decision detail may include labeled images such as:

- committee scorecards;
- candidate comparisons;
- pair diagrams;
- income and performance charts;
- risk charts;
- evidence screenshots;
- lifecycle or replacement timelines.

Images supplement structured scores and reasons and must include path, caption, and image type.

### 7. KPI Tab Simplification

The approved tab set is:

1. Executive Summary
2. Portfolio
3. Watchlist
4. Income
5. Alerts
6. Decision Journal

Performance is consolidated into Executive Summary with deeper analytics behind `More Details`. Holdings is consolidated into Portfolio.

## Implementation

- `src/dividend_bot/strategy_decision_journal.py`
- `tests/test_strategy_decision_journal.py`
- `docs/specifications/STRATEGY_DECISION_JOURNAL_UI_AND_DATA_CONTRACT_V1.md`

## Image Record

The approved Phase 4 visual direction uses:

- a single dark left navigation;
- scan-first Executive Dashboard cards;
- a selected strategy KPI workspace;
- six distinct strategy tabs;
- a newest-first Decision Journal detail experience;
- images inside expanded journal entries.

Repository-maintained screenshots and journal mockups must be stored under:

```text
docs/decisions/2026/08/images/
```

Suggested filenames for the next visual documentation commit:

- `strategy-kpi-navigation-approved.png`
- `dividend-decision-journal-pair-detail.png`
- `swing-decision-journal-opportunity-detail.png`
- `decision-journal-evidence-gallery.png`

## Test Commands

```cmd
python -m py_compile src\dividend_bot\strategy_decision_journal.py
python -m pytest tests\test_strategy_decision_journal.py -v
```

Expected focused result:

```text
8 passed
0 failed
```

## Deployment Verification

On the DigitalOcean staging preview:

- choose Dividend and open Decision Journal;
- verify only Dividend ecosystem decisions appear;
- verify latest decisions are first;
- verify the selected income and leverage legs and their alternatives are visible;
- verify underlying context does not replace the product comparison;
- verify images open with captions;
- choose Swing and verify only Swing decisions appear;
- verify the page remains paper-only and read-only.
