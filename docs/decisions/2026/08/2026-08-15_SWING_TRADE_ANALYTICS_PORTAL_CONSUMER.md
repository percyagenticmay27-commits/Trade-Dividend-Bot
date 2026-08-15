# 2026-08-15 Enterprise Swing Trade Analytics Consumer Decision

## Scope

Trade-Dividend-Bot Enterprise AI CIO consumer only on
`feature/dashboard-refresh-discovery-summary`. Trade-Swing-Bot is unchanged.

## Decision

SWING-001 uses a strategy-specific Trade Analytics / Position Performance
presentation instead of the Dividend Income presentation.

The existing workspace route and `income` tab identifier remain stable for
backward compatibility, but the SWING-001 button label and panel body are replaced
with Trade Analytics. DIVIDEND-001 continues using the existing Income renderer.

## Evidence authority

1. Registry v2 must declare SWING-001 capability `trade_analytics`.
2. Prefer the registered dedicated JSON artifact
   `results/swing_trade_analytics_report.json`.
3. Fall back to registered `enterprise_strategy_kpis.json.trade_analytics`.
4. Resolve relative paths against the external strategy's registered
   `repository_root`.
5. Reject paths outside that root.
6. Never copy or edit generated Swing results in the Dividend repository.

## Presentation rules

- Render authoritative open positions and authentic closed positions only.
- Never create rows from counts.
- Never infer exit data.
- Never calculate drawdown in the host.
- Require the source policy `AUTHORITATIVE_POSITION_HISTORY_ONLY` and preserve
  `max_drawdown_inference_allowed = false`.
- Display missing optional evidence as `Unavailable`.
- Render gains green and losses red.
- Escape all strategy-owned text.

## Governance locks

- DIVIDEND-001 allocation remains $5,000.
- SWING-001 allocation remains $4,500.
- Paper trading only.
- No live trading, broker execution, order placement, capital movement, Robinhood
  execution, or direct external-strategy mutation.

## Current evidence

The authentic Swing ledger currently reports SOXL and TQQQ as open positions and
zero closed positions. Therefore the portal must not display closed-trade fields
until Swing publishes authentic closed evidence.

## Continuation

Run the focused adapter, Trade Analytics UI, and portal integration tests first.
Then run the complete relevant Enterprise portal suite, refresh Enterprise
evidence, restart `dividend-allocation.service`, and inspect the SWING-001
workspace.
