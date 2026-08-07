from master_portfolio_orchestrator import DEFAULT_INPUT_FILES, STAGE_ORDER
from run_daily_dividend_cycle import STAGE_EXECUTION_PLAN


def test_quality_stage_runs_before_dividend_ranking():
    assert "dividend_quality" in STAGE_ORDER
    assert STAGE_ORDER.index("dividend_quality") < STAGE_ORDER.index("dividend_ranking")
    assert DEFAULT_INPUT_FILES["dividend_quality"] == "dividend_quality_report.json"
    assert STAGE_EXECUTION_PLAN["dividend_quality"] == (
        "src.dividend_bot.dividend_quality_engine",
        "build_dividend_quality_report",
    )


def test_quality_stage_is_reporting_only_by_contract():
    from src.dividend_bot import dividend_quality_engine as engine

    assert engine.PAPER_TRADE_MODE is True
    assert engine.REPORTING_ONLY is True
    assert engine.LIVE_TRADING_ENABLED is False
    assert engine.BROKER_EXECUTION_ENABLED is False
    assert engine.ORDER_PLACEMENT_ENABLED is False
    assert engine.CAPITAL_MOVEMENT_ENABLED is False
    assert engine.AUTOMATIC_ACTIVATION_ALLOWED is False
