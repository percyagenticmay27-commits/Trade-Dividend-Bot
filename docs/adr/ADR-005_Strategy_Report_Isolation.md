# ADR-005 Strategy Report Isolation

**Status:** ACCEPTED  
**Version:** 1.0.0

## Decision

Every strategy owns a separate reporting history. Dividend, Swing, Options, and future strategy reports must not be merged into one strategy report.

## Rules

- Each report includes `strategy_id`, `strategy_name`, `strategy_version`, report type, and reporting period.
- Dividend weekly and monthly reports contain only Dividend decisions, positions, income, returns, risks, learning, and recommendations.
- Swing weekly and monthly reports contain only Swing trades, returns, risks, learning, and recommendations.
- Strategy audits remain separate under the same rule.
- Shared templates and renderers are permitted.
- Platform-level summaries may show multiple strategies only in explicitly separated sections with no blended decisions or unattributed returns.

## Rationale

Strategies may hold the same security while using different entry, exit, holding, allocation, and risk policies. Combined reporting would distort accountability and learning.

## Consequences

Storage paths, report models, portfolio attribution, audits, archives, and tests must enforce explicit strategy scope.