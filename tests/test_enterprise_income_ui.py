from __future__ import annotations

from src.dividend_bot.enterprise_income_ui import income_ui_css, render_income_panel


def _row() -> dict:
    return {
        "income": 11.25,
        "net_income_received": 11.25,
        "gross_distribution_income": 12.50,
        "income_adjustments": -1.25,
        "projected_annual_income": 120.0,
        "income_sleeve_reinvestment": 6.25,
        "growth_sleeve_reinvestment": 6.25,
        "holdings": [
            {
                "symbol": "AAA",
                "name": "Alpha Income ETF",
                "yearly_distribution_yield_percent": 25.0,
                "annual_income": 90.0,
                "payment_frequency": "WEEKLY",
                "next_ex_dividend_date": None,
                "income_analytics_source": "market_data_snapshot.json",
            },
            {
                "symbol": "BBB",
                "name": "Beta Income ETF",
                "dividend_yield_percent": 8.0,
                "annual_income": 30.0,
                "payment_frequency": "MONTHLY",
                "next_ex_dividend_date": "2026-08-15",
                "income_analytics_source": "market_data_snapshot.json",
            },
        ],
        "income_events": [
            {
                "date": "2026-08-01",
                "symbol": "AAA",
                "event_type": "DIVIDEND_RECEIVED",
                "amount": 12.50,
                "income_destination_symbol": "AAA",
                "income_destination_amount": 6.25,
                "growth_destination_symbol": "BBB",
                "growth_destination_amount": 6.25,
                "source": "paper_trade_log.csv",
            },
            {
                "date": "2026-08-02",
                "symbol": "AAA",
                "event_type": "DIVIDEND_REVERSAL",
                "amount": -1.25,
                "source": "paper_trade_log.csv",
            },
        ],
    }


def test_income_renderer_uses_professional_summary_cards() -> None:
    output = render_income_panel(_row())
    assert "Net Income Received" in output
    assert "$11.25" in output
    assert "Gross Distributions" in output
    assert "$12.50" in output
    assert "Income Adjustments" in output
    assert "-$1.25" in output
    assert "Projected Annual Income" in output
    assert "$120.00" in output
    assert "Projected Monthly Income" in output
    assert "$10.00" in output
    assert "Income-Producing Positions" in output
    assert ">2<" in output
    assert "Reinvested to Income Sleeve" in output
    assert "Reinvested to Growth Sleeve" in output
    assert "Next Reported Ex-Date" in output
    assert "2026-08-15" in output


def test_income_renderer_uses_strategy_owned_holding_projection_table() -> None:
    output = render_income_panel(_row())
    assert "Income by Holding" in output
    assert "Yearly Distribution Yield" in output
    assert "Alpha Income ETF" in output
    assert "25.00%" in output
    assert "$90.00" in output
    assert "WEEKLY" in output
    assert "Not reported" in output


def test_income_renderer_keeps_realized_and_projected_income_separate() -> None:
    output = render_income_panel(_row())
    assert "Projected income is not treated as realized income" in output
    assert "Distribution History" in output
    assert "DIVIDEND_RECEIVED" in output
    assert "DIVIDEND_REVERSAL" in output
    assert "paper_trade_log.csv" in output
    assert "AAA +$6.25" in output
    assert "BBB +$6.25" in output


def test_income_renderer_preserves_positive_and_negative_realized_events() -> None:
    output = render_income_panel(_row())
    assert "+$12.50" in output
    assert "-$1.25" in output
    assert "income-positive" in output
    assert "income-negative" in output


def test_income_renderer_does_not_fabricate_missing_values() -> None:
    output = render_income_panel({"income": 0.0, "holdings": [], "income_events": []})
    assert "$0.00" in output
    assert "Projected Annual Income" in output
    assert "Not reported" in output
    assert "No strategy-owned income projection evidence is currently reported" in output
    assert "No realized distribution receipt or 50/50 reinvestment has been recorded yet" in output


def test_income_renderer_escapes_strategy_owned_text() -> None:
    row = _row()
    row["holdings"][0]["name"] = "<script>alert(1)</script>"
    output = render_income_panel(row)
    assert "<script>alert(1)</script>" not in output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in output


def test_income_css_is_responsive_and_self_contained() -> None:
    css = income_ui_css()
    assert ".income-summary-grid" in css
    assert ".income-table-wrap" in css
    assert ".income-positive" in css
    assert ".income-negative" in css
    assert "overflow-x:auto" in css
    assert "@media(max-width:520px)" in css


def test_income_renderer_explains_state_to_ledger_mismatch() -> None:
    row = _row()
    row["income_reconciliation_status"] = "MISMATCH"
    row["income_reconciliation_difference"] = 7.50
    output = render_income_panel(row)
    assert "Income ledger needs review" in output
    assert "differ by +$7.50" in output
    assert "does not invent a missing receipt" in output
