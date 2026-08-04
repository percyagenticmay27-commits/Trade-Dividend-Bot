# Robinhood Read-Only Market-Data Fallback Implementation Notes

This change adds a provider-chain boundary to the Dividend Bot market-data service.

## Behavior

- Yahoo Finance remains the primary source.
- Robinhood Agent historical OHLCV may be injected as a read-only fallback.
- Existing stale cache remains the final fallback.
- Dividend-event history does not use Robinhood OHLCV because the verified operation does not expose dividend events.

## Safety

- Paper trade mode remains enabled.
- Live trading remains disabled.
- Broker execution remains disabled.
- Order placement remains disabled.
- No Robinhood order, transfer, cancellation, or position-management operation is referenced.

## Runtime requirement

The repository cannot call the MCP plugin as a shell command or public REST API. The deployed Agentic runtime must supply the callable used by `RobinhoodAgentProvider`.

## Validation commands

```cmd
python -m py_compile robinhood_agent_provider.py
python -m py_compile market_data_provider.py
python -m pytest test_robinhood_agent_provider.py -v
```
