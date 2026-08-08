from src.dividend_bot.dividend_position_lifecycle import (
    build_position_lifecycle,
    enrich_current_holdings_with_lifecycle,
)


def test_reconstructs_open_parked_and_closed_lifecycle() -> None:
    rows = [
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "AMDW", "Pair": "AMDW / AMDL", "Sleeve": "A"},
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "PLTW", "Pair": "PLTW / PLTU", "Sleeve": "A"},
        {"Date": "2026-06-18", "Action": "PAPER_PARK_IN_SGOV", "Ticker": "PLTW", "Pair": "PLTW / PLTU", "Sleeve": "A"},
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Sleeve": "A"},
        {"Date": "2026-06-26", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Sleeve": "A"},
    ]
    holdings = [
        {"symbol": "AMDW", "pair": "AMDW / AMDL", "sleeve": "A", "position_status": "OPEN", "market_value": 52.0},
        {"symbol": "SGOV", "pair": "CASH RESERVE", "sleeve": "RESERVE", "position_status": "PARKED", "market_value": 400.0},
    ]

    lifecycle = build_position_lifecycle(rows, holdings)
    by_symbol = {item["symbol"]: item for item in lifecycle}

    assert by_symbol["AMDW"]["lifecycle_status"] == "OPEN"
    assert by_symbol["AMDW"]["is_current_holding"] is True
    assert by_symbol["PLTW"]["lifecycle_status"] == "PARKED_IN_SGOV"
    assert by_symbol["PLTW"]["is_current_holding"] is False
    assert by_symbol["AVGW"]["lifecycle_status"] == "PARKED_IN_SGOV"
    assert by_symbol["AVGW"]["last_exit_date"] == "2026-06-26"
    assert by_symbol["SGOV"]["lifecycle_status"] == "RESERVE"
    assert by_symbol["SGOV"]["reserve_value"] == 400.0


def test_legacy_park_row_with_sgov_ticker_maps_back_to_pair_sleeve() -> None:
    rows = [
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "PLTW", "Pair": "PLTW / PLTU", "Sleeve": "A"},
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "PLTU", "Pair": "PLTW / PLTU", "Sleeve": "B"},
        {"Date": "2026-06-18", "Action": "PAPER_PARK_IN_SGOV", "Ticker": "SGOV", "Pair": "PLTW / PLTU", "Sleeve": "A", "Paper_Value": "28.0"},
        {"Date": "2026-06-18", "Action": "PAPER_PARK_IN_SGOV", "Ticker": "SGOV", "Pair": "PLTW / PLTU", "Sleeve": "B", "Paper_Value": "12.0"},
    ]

    lifecycle = build_position_lifecycle(rows, [])
    by_symbol = {item["symbol"]: item for item in lifecycle}

    assert by_symbol["PLTW"]["lifecycle_status"] == "PARKED_IN_SGOV"
    assert by_symbol["PLTW"]["last_exit_action"] == "PAPER_PARK_IN_SGOV"
    assert by_symbol["PLTW"]["last_exit_value"] == 28.0
    assert by_symbol["PLTU"]["lifecycle_status"] == "PARKED_IN_SGOV"
    assert by_symbol["PLTU"]["last_exit_value"] == 12.0
    assert "SGOV" not in by_symbol


def test_reentry_is_distinguished_from_first_open_position() -> None:
    rows = [
        {"Date": "2026-06-01", "Action": "PAPER_BUY_OPEN", "Ticker": "TEST"},
        {"Date": "2026-06-10", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "TEST"},
        {"Date": "2026-07-01", "Action": "PAPER_BUY_OPEN", "Ticker": "TEST"},
    ]
    holdings = [{"symbol": "TEST", "sleeve": "A", "purchase_date": "2026-07-01", "market_value": 10.0}]

    lifecycle = build_position_lifecycle(rows, holdings)
    record = lifecycle[0]

    assert record["lifecycle_status"] == "REENTERED"
    assert record["first_purchase_date"] == "2026-06-01"
    assert record["current_open_date"] == "2026-07-01"
    assert record["last_exit_date"] == "2026-06-10"
    assert record["reentry_count"] == 1


def test_enrichment_never_reintroduces_historical_positions_as_current_holdings() -> None:
    holdings = [{"symbol": "AMDW", "sleeve": "A", "position_status": "OPEN"}]
    lifecycle = [
        {"symbol": "AMDW", "lifecycle_status": "OPEN", "first_purchase_date": "2026-06-18", "current_open_date": "2026-06-18", "last_exit_date": None, "reentry_count": 0, "evidence_source": "paper_trade_log.csv"},
        {"symbol": "PLTW", "lifecycle_status": "PARKED_IN_SGOV", "first_purchase_date": "2026-06-18", "current_open_date": None, "last_exit_date": "2026-06-18", "reentry_count": 0, "evidence_source": "paper_trade_log.csv"},
    ]

    enriched = enrich_current_holdings_with_lifecycle(holdings, lifecycle)

    assert [item["symbol"] for item in enriched] == ["AMDW"]
    assert enriched[0]["lifecycle_status"] == "OPEN"
    assert enriched[0]["lifecycle_first_purchase_date"] == "2026-06-18"


def test_safety_flags_remain_paper_only() -> None:
    import src.dividend_bot.dividend_position_lifecycle as module

    assert module.PAPER_TRADE_MODE is True
    assert module.REPORTING_ONLY is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
