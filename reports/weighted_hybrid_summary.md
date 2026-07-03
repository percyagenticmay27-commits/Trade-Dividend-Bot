# Weighted Hybrid Portfolio Summary

## Portfolio Results

| Portfolio_Type | Starting_Capital | Ending_Capital | Profit_Loss | Return_Pct | Max_Drawdown | Average_Drawdown | Dividends_Received | Earnings_Exits | SGOV_Entries | Days_In_SGOV |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Equal_Weight_Hybrid | 500.0000 | 551.0099 | 51.0099 | 10.2020 | -16.1910 | -25.1378 | 35.9877 | 18.0000 | 34.0000 | 730.0000 |
| Strength_Weighted_Hybrid | 500.0000 | 609.3133 | 109.3133 | 21.8627 | -11.3722 | -22.3567 | 40.7906 | 18.0000 | 34.0000 | 730.0000 |
| Risk_Adjusted_Hybrid | 500.0000 | 657.2066 | 157.2066 | 31.4413 | -8.7580 | -19.3724 | 42.9712 | 18.0000 | 34.0000 | 730.0000 |

## Rankings

| Portfolio_Type | Ending_Capital | Return_Pct | Max_Drawdown | Return_Drawdown_Ratio | Ending_Rank | Return_Rank | Drawdown_Rank | Ratio_Rank | Overall_Rank_Sum |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Risk_Adjusted_Hybrid | 657.2066 | 31.4413 | -8.7580 | 3.5900 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 4.0000 |
| Strength_Weighted_Hybrid | 609.3133 | 21.8627 | -11.3722 | 1.9225 | 2.0000 | 2.0000 | 2.0000 | 2.0000 | 8.0000 |
| Equal_Weight_Hybrid | 551.0099 | 10.2020 | -16.1910 | 0.6301 | 3.0000 | 3.0000 | 3.0000 | 3.0000 | 12.0000 |

- Best Overall Portfolio: Risk_Adjusted_Hybrid
- Improvement vs Equal Weight: $+106.196672
- Improvement Percent: +19.273097%

## Strength-Weighted Allocations

| Pair | Allocation |
| --- | --- |
| AMDW / AMDL | 75.0000 |
| AVGW / AVGX | 60.0000 |
| GOOW / GGLL | 60.0000 |
| NVDW / NVDX | 55.0000 |
| GLDW / NUGT | 50.0000 |
| NFLW / NFLU | 50.0000 |
| TSLW / TSLL | 45.0000 |
| PLTW / PLTU | 40.0000 |
| COIW / CONL | 35.0000 |
| MST / XXRP | 30.0000 |

## Risk-Adjusted Allocations

Negative scores receive the $20 minimum. Remaining capital is distributed across positive scores with a $90 cap.

| Pair | Raw_Score | Allocation |
| --- | --- | --- |
| AMDW / AMDL | 6.4989 | 90.0000 |
| GOOW / GGLL | 1.8940 | 90.0000 |
| NFLW / NFLU | 1.3985 | 81.2276 |
| AVGW / AVGX | 1.1115 | 68.6620 |
| GLDW / NUGT | 0.7359 | 52.2191 |
| NVDW / NVDX | 0.4087 | 37.8913 |
| COIW / CONL | -0.8392 | 20.0000 |
| PLTW / PLTU | -0.6588 | 20.0000 |
| TSLW / TSLL | -0.3103 | 20.0000 |
| MST / XXRP | -0.8246 | 20.0000 |

The risk-adjusted allocation is an in-sample optimization because its scores use returns and drawdowns from the evaluated period.

## Final Answer

Yes for continued backtesting: weighting materially improved ending capital and return/drawdown efficiency without worsening max drawdown. No for an immediate live-allocation change: the risk-adjusted weights were fitted to this same backtest period, so they require out-of-sample or walk-forward validation first.

## Validation

- Every portfolio starts with exactly $500.
- All pair allocations sum to $500.
- Risk-adjusted allocations remain between $20 and $90.
- Hybrid pair architecture and independent-pair selections are unchanged.
- Dividend totals scale with capital and reconcile to pair results.
- Earnings and SGOV event counts reconcile to the hybrid components.
