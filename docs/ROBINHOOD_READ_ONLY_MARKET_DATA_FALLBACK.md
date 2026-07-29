# Robinhood Read-Only Market-Data Fallback

## Purpose

Add a read-only historical OHLCV fallback behind Yahoo Finance without enabling brokerage execution, order placement, cancellation, transfers, or position management.

## Provider chain

```text
Yahoo Finance
    ↓ failure
Robinhood Agent read-only historicals
    ↓ failure
Prior stale cache
```

Dividend events remain Yahoo/cache sourced because the verified Robinhood operation returns historical OHLCV bars, not dividend-event history.

## Verified operation

- Operation: `mcp__codex_apps__robinhood_etf_tradebot_get_equity_historicals`
- Plugin app ID: `plugin_asdk_app_6a3419ec40fc8191b59c55b9355dc1da`
- Maximum symbols per request: 10
- Interval used: `day`
- Bounds used: `regular`
- Adjustment request: `split`

Example request:

```json
{
  "symbols": ["SPY"],
  "start_time": "2025-01-01T00:00:00Z",
  "end_time": "2026-07-29T23:59:59Z",
  "interval": "day",
  "bounds": "regular",
  "adjustment_type": "split"
}
```

## Runtime boundary

The Robinhood plugin is an MCP/ChatGPT operation, not a public REST endpoint or shell command. The deployed Agentic runtime must inject a callable into `RobinhoodAgentProvider` with this interface:

```python
invoker(operation_name: str, payload: Mapping[str, Any]) -> Mapping[str, Any]
```

The provider never stores Robinhood credentials and never invents an HTTP URL.

## Normalization

- `Date` = date portion of `begins_at`
- `Open` = `open_price`
- `High` = `high_price`
- `Low` = `low_price`
- `Close` = `close_price`
- `Adj Close` = `close_price`
- `Volume` = `volume`

Bars with `interpolated=true` are ignored. Current-day bars are excluded to avoid incomplete daily candles.

Robinhood fallback records always disclose:

```text
adjusted_close_source = UNAVAILABLE_USE_CLOSE
corporate_action_adjusted = false
```

The adapter does not silently claim that Robinhood history is fully adjusted for every corporate action.

## Permanent safety boundary

```text
paper_trade_mode = true
live_trading_enabled = false
broker_execution_enabled = false
order_placement_enabled = false
read_only_market_data = true
```

The adapter exposes only quote and historical read methods. It exposes no order, cancellation, transfer, execution, or position-management methods.

## Usage

```python
from market_data_provider import MarketDataService
from robinhood_agent_provider import RobinhoodAgentProvider
from yahoo_finance_provider import YahooFinanceProvider

robinhood = RobinhoodAgentProvider(invoker=agentic_mcp_invoker)
service = MarketDataService(
    root_path=".",
    provider=YahooFinanceProvider(),
    fallback_provider=robinhood,
)

history = service.get_history("SPY", period="1y", interval="1d", force_refresh=True)
```

## Validation

```cmd
python -m py_compile robinhood_agent_provider.py
python -m py_compile market_data_provider.py
python -m pytest test_robinhood_agent_provider.py -v
```

## Deployment requirement

The repository code is ready to use the fallback only after the deployed Agentic runtime provides the verified MCP invoker. Without that runtime bridge, Yahoo Finance and cache behavior remain unchanged and no Robinhood call is attempted.
