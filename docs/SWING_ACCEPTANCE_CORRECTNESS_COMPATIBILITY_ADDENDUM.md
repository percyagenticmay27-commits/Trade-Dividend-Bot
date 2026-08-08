# Swing Acceptance Correctness Compatibility Addendum

## Purpose

Record Enterprise display/evidence contracts introduced while repairing Dividend acceptance findings. This document does not modify the Swing repository and does not require Swing to copy Dividend-specific SGOV mechanics.

## 1. Enterprise Capital Contract

The host AI CIO allocation is authoritative. A strategy runtime must not silently manage a different hard-coded capital amount while Enterprise reports the host allocation.

Swing should publish or consume enough evidence to reconcile:

- Enterprise allocated capital
- strategy portfolio value
- invested capital
- reserve/cash capital
- any intentional unallocated capital

The displayed allocation must have no unexplained remainder.

## 2. Historical Lifecycle Deduplication

Repeated refresh/reinitialization rows must not double count entry capital, exits, realized P&L, or re-entry counts. Historical transaction identity should be deterministic and duplicate-safe.

## 3. NEVER_ENTERED Classification

A candidate evaluated but never given actual paper exposure must not appear in Position / Sales History as a zero-return completed trade. Swing may use its own terminology, but Enterprise compatibility should distinguish at least:

- actually opened positions
- completed/closed positions
- candidates that never entered

Dividend-specific `WAIT_IN_SGOV` is not a required Swing state.

## 4. Yield / Metric Denominator Auditability

When a UI metric states that it uses a current price or current portfolio value, the denominator must be the same authoritative value displayed to the user or must explicitly disclose a different source and as-of date.

Swing should apply the same auditability principle to ROI, risk, opportunity, performance, and other derived metrics.

## Enterprise Display Principle

A feature is accepted only when source evidence, Enterprise KPI output, rendered UI, calculations, empty-state behavior, and cross-strategy isolation agree.
