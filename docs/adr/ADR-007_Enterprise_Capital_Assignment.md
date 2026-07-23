# ADR-007 Enterprise Capital Assignment

**Version:** 1.0.0  
**Status:** ACCEPTED

## Context

A brokerage account exposes one cash balance while the platform may host multiple independent strategies such as Dividend, Swing, Options, and Futures. Strategy portfolio managers must not guess how unassigned account cash should be divided.

## Decision

Introduce an Enterprise Capital Manager above strategy portfolio managers.

The Enterprise CIO may inspect installed strategy definitions and produce a non-binding allocation recommendation. The investor must approve the actual assignment of cash to one or more strategies. The Enterprise Capital Manager records the approved assignment in an append-only capital allocation ledger and exposes each strategy's assigned capital balance.

## Permanent Rules

- Unassigned cash remains enterprise cash until the investor approves an assignment.
- The Enterprise CIO may recommend but may not silently allocate investor cash.
- Only installed and operational or paper-validation-ready strategies may receive new allocations.
- Strategy portfolio managers may use only their assigned strategy capital.
- Deposits, withdrawals, assignments, transfers, and releases are append-only ledger events.
- Strategy returns, reports, audits, and decisions remain isolated.
- Version 1 remains paper-only and creates no brokerage orders.

## Workflow

```text
Brokerage Cash Snapshot
        ↓
Installed Strategy Discovery
        ↓
Enterprise CIO Recommendation (optional)
        ↓
Investor Approval
        ↓
Enterprise Capital Allocation Ledger
        ↓
Strategy Capital Balances
        ↓
Strategy Portfolio Managers
```

## Consequences

This prevents accidental cross-strategy spending, makes capital ownership auditable, supports future deposits and withdrawals, and allows new strategy plugins to appear in the investor allocation interface without changing portfolio accounting.
