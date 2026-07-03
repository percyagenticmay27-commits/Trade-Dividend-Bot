# Walk-Forward Validation Summary

## Results

| Period | Portfolio_Type | Starting_Capital | Ending_Capital | Profit_Loss | Return_Pct | Max_Drawdown | Return_Drawdown_Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Period A | Equal_Weight_Hybrid | 500.000000 | N/A | N/A | N/A | N/A | N/A |
| Period A | Strength_Weighted_Hybrid | 500.000000 | N/A | N/A | N/A | N/A | N/A |
| Period A | Risk_Adjusted_Hybrid | 500.000000 | N/A | N/A | N/A | N/A | N/A |
| Period B | Equal_Weight_Hybrid | 500.000000 | 499.493560 | -0.506440 | -0.101288 | -5.457068 | -0.018561 |
| Period B | Strength_Weighted_Hybrid | 500.000000 | 496.445986 | -3.554014 | -0.710803 | -5.894323 | -0.120591 |
| Period B | Risk_Adjusted_Hybrid | 500.000000 | 503.896844 | 3.896844 | 0.779369 | -4.905328 | 0.158882 |
| Period C | Equal_Weight_Hybrid | 500.000000 | 551.009918 | 51.009918 | 10.201984 | -16.190963 | 0.630104 |
| Period C | Strength_Weighted_Hybrid | 500.000000 | 609.313347 | 109.313347 | 21.862669 | -11.372218 | 1.922463 |
| Period C | Risk_Adjusted_Hybrid | 500.000000 | 657.206597 | 157.206597 | 31.441319 | -8.757960 | 3.590028 |

## Coverage

- Period A: unavailable; no history for AMDW, GLDW, GOOW, AVGW. Requested 2025-01-01 through 2025-06-30.
- Period B: runnable from common inception 2025-10-30 through 2025-12-31; requested start was 2025-07-01.
- Period C: runnable from common inception 2026-01-02 through 2026-06-18; requested start was 2026-01-01.

## Cross-Period Averages

| Portfolio_Type | Average_Return | Average_Max_Drawdown | Average_Return_Drawdown_Ratio |
| --- | --- | --- | --- |
| Risk_Adjusted_Hybrid | 16.110344 | -6.831644 | 1.874455 |
| Strength_Weighted_Hybrid | 10.575933 | -8.633271 | 0.900936 |
| Equal_Weight_Hybrid | 5.050348 | -10.824015 | 0.305771 |

## Questions

1. No. Strength Weighted beat Equal Weight in 1 of 2 runnable periods. A three-period majority cannot be established because Period A is unavailable.
2. Risk Adjusted outperformed Equal Weight in 2 of 2 runnable periods: both shortened Period B and in-sample Period C.
3. Best average return across runnable periods: Risk_Adjusted_Hybrid.
4. Best average drawdown across runnable periods: Risk_Adjusted_Hybrid.
5. Live deployment recommendation: Equal Weight Hybrid until a complete out-of-sample dataset is available. Weighted results may justify a paper-trading candidate, but missing Period A and the shortened Period B do not support live promotion.

## Validation

- Every runnable portfolio starts with exactly $500.
- Pair allocations sum to exactly $500.
- The seven pair-managed and three independent-sleeve assignments are unchanged.
- Dividend and earnings logic runs through the existing validated engines.
- Period A coverage validation failed; no synthetic history or proxy symbols were used.
