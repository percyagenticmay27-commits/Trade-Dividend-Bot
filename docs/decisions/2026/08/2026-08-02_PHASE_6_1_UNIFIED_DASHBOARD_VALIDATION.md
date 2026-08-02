# Phase 6.1 Unified Dashboard Validation Contract

**Date:** 2026-08-02  
**Status:** Implemented; local validation pending

## Decision

Phase 6 begins with one read-only validator for the complete unified Enterprise
dashboard artifact set. The validator verifies continuity from strategy registry
through Executive and Investor dashboard consumers, Enterprise KPI rows, and
strategy-owned Decision Journals.

## Required artifacts

- `enterprise_dividend_service_registry.json`
- `ai_cio_executive_dashboard.json`
- `enterprise_investor_dashboard.json`
- `enterprise_strategy_kpis.json`
- `dividend_strategy_decision_journal.json`
- `swing_strategy_decision_journal.json`

## Validation

- Both `DIVIDEND-001` and `SWING-001` appear independently in every consumer.
- Duplicate or missing strategy IDs fail validation.
- KPI health and allocated capital are visible and valid.
- Journals match their strategy IDs and reject cross-strategy decisions.
- Safe empty journals produce warnings rather than fabricated evidence.
- Executive, Investor, and journal artifacts preserve paper-only safety.
- Results are written as deterministic JSON and Markdown reports.

## Safety and compatibility

The validator reads existing outputs only. It does not import strategy production
code, change calculations, alter allocations or governance, communicate with
Robinhood or another broker, place orders, or move capital. Enterprise KPI
Contract v1.0 remains unchanged.
