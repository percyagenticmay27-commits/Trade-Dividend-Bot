from src.dividend_bot.dividend_position_lifecycle import (
    build_position_lifecycle,
    enrich_current_holdings_with_lifecycle,
)


def test_reconstructs_open_parked_and_closed_lifecycle() -> None:
    rows = [
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "AMDW", "Pair": "AMDW / AMDL", "Sleeve": "A", "Paper_Value": "52.00"},
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "PLTW", "Pair": "PLTW / PLTU", "Sleeve": "A", "Paper_Value": "26.00"},
        {"Date": "2026-06-18", "Action": "PAPER_PARK_IN_SGOV", "Ticker": "PLTW", "Pair": "PLTW / PLTU", "Sleeve": "A", "Paper_Value": "28.00"},
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Sleeve": "A", "Paper_Value": "36.98"},
        {"Date": "2026-06-26", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Sleeve": "A", "Paper_Value": "35.89"},
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
    assert by_symbol["PLTW"]["entry_value"] == 26.0
    assert by_symbol["PLTW"]["last_exit_value"] == 28.0
    assert by_symbol["PLTW"]["realized_gain_loss"] == 2.0
    assert by_symbol["AVGW"]["lifecycle_status"] == "PARKED_IN_SGOV"
    assert by_symbol["AVGW"]["last_exit_date"] == "2026-06-26"
    assert by_symbol["AVGW"]["entry_value"] == 36.98
    assert by_symbol["AVGW"]["realized_gain_loss"] == -1.09
    assert by_symbol["SGOV"]["lifecycle_status"] == "RESERVE"
    assert by_symbol["SGOV"]["reserve_value"] == 400.0


def test_legacy_sgov_parking_row_maps_back_to_pair_sleeve_and_preserves_value() -> None:
    rows = [
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "PLTU", "Pair": "PLTW / PLTU", "Sleeve": "B", "Paper_Value": "10.00"},
        {"Date": "2026-06-18", "Action": "PAPER_PARK_IN_SGOV", "Ticker": "SGOV", "Pair": "PLTW / PLTU", "Sleeve": "B", "Paper_Value": "12.00"},
    ]

    lifecycle = build_position_lifecycle(rows, [])
    record = lifecycle[0]

    assert record["symbol"] == "PLTU"
    assert record["lifecycle_status"] == "PARKED_IN_SGOV"
    assert record["entry_value"] == 10.0
    assert record["last_exit_value"] == 12.0
    assert record["realized_gain_loss"] == 2.0


def test_reentry_uses_only_most_recent_completed_cycle_for_entry_value() -> None:
    rows = [
        {"Date": "2026-06-01", "Action": "PAPER_BUY_OPEN", "Ticker": "TEST", "Paper_Value": "10.00"},
        {"Date": "2026-06-10", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "TEST", "Paper_Value": "12.00"},
        {"Date": "2026-07-01", "Action": "PAPER_BUY_OPEN", "Ticker": "TEST", "Paper_Value": "20.00"},
        {"Date": "2026-07-05", "Action": "PAPER_BUY", "Ticker": "TEST", "Paper_Value": "5.00"},
        {"Date": "2026-07-20", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "TEST", "Paper_Value": "27.50"},
    ]

    lifecycle = build_position_lifecycle(rows, [])
    record = lifecycle[0]

    assert record["entry_value"] == 25.0
    assert record["last_exit_value"] == 27.5
    assert record["realized_gain_loss"] == 2.5
    assert record["reentry_count"] == 1


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


def test_missing_transaction_values_do_not_fabricate_gain_loss() -> None:
    rows = [
        {"Date": "2026-06-01", "Action": "PAPER_BUY_OPEN", "Ticker": "TEST"},
        {"Date": "2026-06-10", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "TEST"},
    ]
    record = build_position_lifecycle(rows, [])[0]
    assert record["entry_value"] is None
    assert record["last_exit_value"] is None
    assert record["realized_gain_loss"] is None


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
