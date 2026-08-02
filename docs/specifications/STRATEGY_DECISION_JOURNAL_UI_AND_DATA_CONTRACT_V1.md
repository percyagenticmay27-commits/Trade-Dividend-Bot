# Strategy Decision Journal UI and Data Contract v1.0

## Purpose

This is the authoritative specification for the **Decision Journal tab inside an individual strategy KPI workspace**.

The Decision Journal is reporting-only, paper-only, read-only, newest-first, explainable, and auditable. It does not place orders, move capital, or combine decisions from unrelated strategies.

## Permanent Scope Rule

The selected KPI workspace controls the journal scope.

- Dividend KPI → Dividend decisions only.
- Swing KPI → Swing decisions only.
- Future Options KPI → Options decisions only.
- Future Futures KPI → Futures decisions only.

A strategy journal must never display another strategy's committee votes, evidence, portfolio decisions, or candidate history.

The Enterprise Investor Dashboard may show high-level decision counts, but detailed entries remain inside the owning strategy KPI.

## Ordering

Entries are ordered by `decision_timestamp` descending.

The most recent decision is always first so the investor can immediately see:

- what changed most recently;
- which investment object was affected;
- why the decision was made;
- whether the decision is pending, approved, monitoring, deferred, replaced, or closed.

## Common Decision Journal Display

Each journal entry shows a compact newest-first summary row or card:

- Date and time
- Decision type
- Decision object
- Status
- Plain-language summary
- Primary score or rank when supplied
- Lifecycle event link when supplied
- `View Evidence` / `More Details`
- Image count or evidence-gallery indicator

Opening an entry shows:

1. Decision summary
2. Selected investment object
3. Alternatives considered
4. Committee scores and evidence
5. Final rationale
6. Lifecycle relationship
7. Images, charts, screenshots, and scorecards
8. Evidence timestamps and freshness

## Dividend Decision Unit — Ecosystem Selection

Dividend decisions are **not underlying-stock decisions**.

An underlying company can provide context, but it does not explain why one linked income product or leveraged product was selected over another.

The Dividend journal must answer questions such as:

> Why was NVDY selected instead of NVDW for the income leg?

> Why was NVDX selected instead of NVDU for the leverage leg?

> Why was the selected income ETF + leverage ETF combination approved as the ecosystem pair?

### Standard Pair Mode

A Dividend ecosystem decision normally contains:

- Ecosystem ID and name
- Selected income leg
- Selected leverage leg
- Other income candidates
- Other leverage candidates
- Income-leg selection reason
- Leverage-leg selection reason
- Pair compatibility reason
- Candidate comparison table
- Pair allocation when reported
- Pair protection and replacement gates when reported
- Dividend committee evidence only

The journal must compare candidates **within their intended role**. An income product is compared against qualified income alternatives. A leveraged product is compared against qualified leverage alternatives.

### Self-Funded Exception

A Dividend ecosystem may use one primary instrument only when the strategy explicitly declares `SELF_FUNDED` mode and supplies a reason explaining how that instrument fulfills the required ecosystem role without a separate pair.

This exception must not be inferred merely because an underlying company is strong.

### Underlying Context

Underlying-company evidence is context-only unless the Dividend strategy explicitly declares it as a scored component.

Underlying context must never replace the product-selection comparison.

## Swing Decision Unit — Individual Opportunity

The Swing journal contains only Swing decisions and Swing committee evidence.

A Swing entry normally contains:

- Symbol or Swing opportunity ID
- Decision type
- Committee rank
- Opportunity Quality
- Entry / Timing score, kept separate
- Strategy assignment when supplied
- Alternatives or challengers
- Swing committee scores
- Swing evidence
- Final Swing rationale

It must not contain Dividend ecosystem pairs or Dividend committee evidence.

## Images and Visual Evidence

The Decision Journal detail view must support images.

Supported examples include:

- Committee scorecard image
- Candidate-comparison image
- Ecosystem pair diagram
- Performance chart
- Income chart
- Risk or drawdown chart
- Evidence screenshot
- Lifecycle timeline image
- Replacement comparison image

Every image reference requires:

- Repository or safely served path
- Caption
- Image type
- Relationship to the decision

Images must be displayed beneath the decision summary in an evidence gallery or individually labeled sections. Images supplement structured evidence; they do not replace machine-readable scores and reasons.

Repository-maintained Decision Journal images belong under:

```text
docs/decisions/YYYY/MM/images/
```

Deployed runtime images may use safe application paths declared by the owning strategy artifact contract.

## Strategy Decision Journal Contract

Implementation:

```text
src/dividend_bot/strategy_decision_journal.py
```

Required document metadata:

- `strategy_id`
- `strategy_name`
- `strategy_kind`
- `journal_scope = SELECTED_STRATEGY_ONLY`
- `sort_order = NEWEST_FIRST`
- `decision_count`
- `paper_trade_mode = true`
- `live_trading_enabled = false`
- `broker_execution_enabled = false`
- `read_only = true`

## Current KPI Tab Set

The approved strategy KPI tabs are:

1. Executive Summary
2. Portfolio
3. Watchlist
4. Income
5. Alerts
6. Decision Journal

Removed as separate tabs:

- Performance — its essential information remains in Executive Summary, with deeper performance analytics available through `More Details`.
- Holdings — holdings are part of Portfolio.

## Acceptance Criteria

1. Decision entries are newest first.
2. Selecting the Swing KPI shows no Dividend decisions.
3. Selecting the Dividend KPI shows no Swing decisions.
4. Dividend pair decisions require both selected roles and role-specific reasons.
5. Dividend pair decisions show role-specific alternatives.
6. Underlying-stock context cannot substitute for choosing among linked products.
7. A one-instrument Dividend ecosystem requires an explicit self-funded declaration and reason.
8. Swing decisions preserve Opportunity Quality and Entry / Timing as separate values.
9. Every entry may display labeled images and visual evidence.
10. Missing evidence is labeled and never invented.
11. The journal remains paper-only, read-only, and unable to execute trades.

## DigitalOcean Verification

On `allocation.jshouseapi.com` or the approved staging route, verify:

- The selected strategy name appears in the Decision Journal header.
- The journal is newest first.
- Only the selected strategy's entries are present.
- Dividend entries show ecosystem pair selection rather than a generic underlying-stock decision.
- NVDY-versus-NVDW and NVDX-versus-NVDU style comparisons can be rendered when supplied.
- Swing entries show only Swing opportunity evidence.
- `View Evidence` opens scores, reasons, alternatives, and images.
- No journal action implies live execution.
