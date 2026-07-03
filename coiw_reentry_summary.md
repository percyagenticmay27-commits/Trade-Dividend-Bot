# COIW / CONL A-Only Re-entry Test

## Result

- Best Model: ETF
- Best Re-entry Mode: proportional
- Best Final Value: $26.509570
- Best Return: -46.980861%
- Underlying A-only vs proportional: $+0.647543
- Underlying A-only vs fixed 70/30: $+0.820196
- ETF A-only vs proportional: $+0.000000
- ETF note: no SGOV exit occurred, so re-entry mode was not exercised.

## Comparison

| Pair | Model | Reentry_Mode | Final_Value | Profit_Loss | Return_Pct | Max_Drawdown | Dividends_Received | Dividends_Reinvested_A | Dividends_Reinvested_B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COIW / CONL | Underlying | proportional | 22.2158 | -27.7842 | -55.5685 | -60.1879 | 2.8568 | 1.2806 | 1.2806 |
| COIW / CONL | Underlying | fixed_70_30 | 22.0431 | -27.9569 | -55.9138 | -60.4973 | 2.7815 | 1.2559 | 1.2559 |
| COIW / CONL | ETF | proportional | 26.5096 | -23.4904 | -46.9809 | -55.9824 | 1.9704 | 0.9852 | 0.9852 |
| COIW / CONL | ETF | fixed_70_30 | 26.5096 | -23.4904 | -46.9809 | -55.9824 | 1.9704 | 0.9852 | 0.9852 |
| COIW / CONL | Underlying | a_only_reentry | 22.8633 | -27.1367 | -54.2734 | -59.0274 | 3.1391 | 1.3739 | 1.3739 |
| COIW / CONL | ETF | a_only_reentry | 26.5096 | -23.4904 | -46.9809 | -55.9824 | 1.9704 | 0.9852 | 0.9852 |

## Validation

- A-only SGOV principal re-entry allocated 100% to COIW.
- CONL received only its approved 50% dividend reinvestment.
- Profit/loss, return, trade, and SGOV counters reconciled.
