# Hybrid Portfolio Summary

- Total starting capital: $500.00
- Hybrid ending capital: $551.009896
- Hybrid profit/loss: $+51.009896
- Hybrid return: +10.201979%
- Hybrid portfolio max drawdown: -16.190966%
- Hybrid average pair drawdown: -25.137808%
- Dividends received: $35.987675
- Earnings exits: 18
- SGOV entries: 34
- SGOV pair-days: 730
- Best pair: AMDW / AMDL ($122.068477)
- Worst pair: COIW / CONL ($26.509570)

## Comparison vs Current Best

- Current best ending capital: $545.851548
- Difference dollars: $+5.158348
- Difference percent: +0.945009%
- Current portfolio max drawdown: -16.190966%
- Max drawdown change: +0.000000 percentage points

## Hybrid Pair Components

| Pair | Architecture | Final_Value | Return_Pct | Max_Drawdown | Dividends_Received | Earnings_Exits | SGOV_Entries | Days_In_SGOV |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AMDW / AMDL | pair_underlying_proportional | 122.0685 | 144.1370 | -22.1787 | 10.1970 | 2.0000 | 4.0000 | 50.0000 |
| GLDW / NUGT | pair_underlying_proportional | 57.9163 | 15.8325 | -21.5141 | 2.7222 | 0.0000 | 1.0000 | 65.0000 |
| NVDW / NVDX | pair_underlying_proportional | 53.5589 | 7.1177 | -17.4174 | 4.3394 | 2.0000 | 5.0000 | 51.0000 |
| GOOW / GGLL | independent_sleeves | 57.6086 | 15.2171 | -8.0344 | 3.0402 | 4.0000 | 7.0000 | 72.0000 |
| NFLW / NFLU | pair_underlying_proportional | 57.0644 | 14.1288 | -10.1029 | 1.2995 | 2.0000 | 4.0000 | 88.0000 |
| AVGW / AVGX | pair_underlying_proportional | 60.5107 | 21.0214 | -18.9128 | 5.2873 | 2.0000 | 3.0000 | 43.0000 |
| COIW / CONL | independent_sleeves | 26.5096 | -46.9809 | -55.9824 | 1.9704 | 2.0000 | 2.0000 | 88.0000 |
| PLTW / PLTU | pair_underlying_proportional | 41.0191 | -17.9619 | -27.2632 | 1.4137 | 1.0000 | 1.0000 | 96.0000 |
| TSLW / TSLL | pair_underlying_proportional | 47.8257 | -4.3486 | -14.0154 | 2.5533 | 1.0000 | 3.0000 | 84.0000 |
| MST / XXRP | independent_sleeves | 26.9283 | -46.1435 | -55.9566 | 3.1646 | 2.0000 | 4.0000 | 93.0000 |

## Validation

- Portfolio starts with 10 x $50 = $500.
- Hybrid ending capital equals the sum of its 10 selected pair values.
- Pair-managed rows match Underlying/proportional earnings results.
- Independent rows match the validated independent-sleeve results.
- MST/XXRP remains unchanged and independent.
- Dividend and earnings totals reconcile to selected pair rows.
