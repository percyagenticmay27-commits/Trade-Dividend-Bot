# Robinhood Read-Only Market-Data Fallback Test Plan

Required checks:

1. Yahoo history success does not invoke Robinhood.
2. Yahoo history failure invokes Robinhood.
3. Robinhood response fields normalize to the existing Dividend Bot history schema.
4. Interpolated bars are ignored.
5. Incomplete current-day bars are excluded.
6. Invalid OHLC relationships fail validation.
7. Duplicate dates fail validation.
8. Robinhood `not_found` entries become provider failures.
9. Robinhood failure falls through to stale cache when available.
10. Dividend-event retrieval never invokes the Robinhood OHLCV operation.
11. The adapter exposes no order, cancellation, transfer, or position-management method.
12. Safety flags remain paper-only and execution-disabled.
