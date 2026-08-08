import csv
from pathlib import Path

from src.dividend_bot.dividend_dashboard_evidence import build_dividend_dashboard_evidence


def test_dashboard_uses_transaction_ledger_for_realized_income(tmp_path: Path) -> None:
    with (tmp_path / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Action", "Ticker", "Pair", "Paper_Value"])
        writer.writeheader()
        writer.writerow({"Date": "2026-08-01", "Action": "PAPER_DIVIDEND_RECEIVED", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Paper_Value": "2.50"})
        writer.writerow({"Date": "2026-08-02", "Action": "PAPER_DIVIDEND_REVERSAL", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Paper_Value": "0.50"})

    report = build_dividend_dashboard_evidence(tmp_path)

    assert report["gross_distribution_income"] == 2.50
    assert report["income_adjustments"] == -0.50
    assert report["net_income_received"] == 2.00
    assert report["income"] == 2.00
    assert len(report["income_events"]) == 2
    assert report["income_accounting_method"] == "PAPER_TRANSACTION_LEDGER_NET_OF_ADJUSTMENTS"


def test_dashboard_does_not_mix_trade_sale_value_into_income(tmp_path: Path) -> None:
    with (tmp_path / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Action", "Ticker", "Pair", "Paper_Value"])
        writer.writeheader()
        writer.writerow({"Date": "2026-08-01", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Paper_Value": "99.00"})

    report = build_dividend_dashboard_evidence(tmp_path)
    assert report["income"] == 0.0
    assert report["gross_distribution_income"] == 0.0
    assert report["income_adjustments"] == 0.0
    assert report["income_events"] == []
