# Phase 4.3 Enterprise Decision Canonicalization Decision Log

**Date:** 2026-08-01  
**Status:** Accepted and implemented

## Decision

Strategy bots remain responsible only for their own domain models and decision evidence. The Enterprise Integration Layer translates strategy-native decision events into the canonical AI CIO Decision Journal contract.

## Strategy isolation

- Swing continues publishing Swing opportunity fields such as symbol, committee rank, Opportunity Quality, Entry Score, alternatives, and Swing committee evidence.
- Swing does not implement Dividend ecosystem, income-leg, or leverage-leg fields.
- Dividend may publish compact ecosystem aliases or canonical fields.
- Future Options and Futures strategies will retain their own domain-native objects and receive separate Enterprise adapters.

## Dividend compatibility

The Enterprise canonicalizer accepts:

- compact raw fields such as `ecosystem` and `ecosystem_node`;
- canonical top-level fields such as `ecosystem_id`, `ecosystem_name`, and `ecosystem_mode`;
- already-normalized records whose pair fields are nested beneath `ecosystem`.

All accepted forms normalize to one strict canonical Dividend ecosystem object. Required pair evidence remains mandatory.

## Idempotence rule

A normalized decision may be validated and normalized again without losing fields or changing meaning. This is required because publication stores canonical records and journal generation validates stored records again.

## Safety

This layer is reporting-only and paper-only. It does not calculate scores, select investments, move capital, or execute trades.

## Deployment troubleshooting

If a published Dividend decision fails during journal generation with a missing pair field even though publication succeeded, confirm the deployed version includes:

- `src/dividend_bot/enterprise_strategy_decision_canonicalizer.py`
- `strategy_decision_journal.py` module version 1.0.2 or later
- the nested canonical record idempotence test
