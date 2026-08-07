from master_portfolio_orchestrator import DEFAULT_INPUT_FILES, STAGE_ORDER
from run_daily_dividend_cycle import STAGE_EXECUTION_PLAN


COMPONENT_STAGES = (
    "dividend_quality",
    "dividend_growth",
    "dividend_safety",
    "valuation",
)


def test_all_opportunity_components_run_before_dividend_ranking():
    ranking_index = STAGE_ORDER.index("dividend_ranking")
    for stage in COMPONENT_STAGES:
        assert stage in STAGE_ORDER
        assert STAGE_ORDER.index(stage) < ranking_index

    assert DEFAULT_INPUT_FILES["dividend_quality"] == "dividend_quality_report.json"
    assert DEFAULT_INPUT_FILES["dividend_growth"] == "dividend_growth_report.json"
    assert DEFAULT_INPUT_FILES["dividend_safety"] == "dividend_safety_report.json"
    assert DEFAULT_INPUT_FILES["valuation"] == "valuation_report.json"


def test_stage_execution_plan_uses_read_only_component_engines():
    assert STAGE_EXECUTION_PLAN["dividend_quality"] == (
        "src.dividend_bot.dividend_quality_engine",
        "build_dividend_quality_report",
    )
    assert STAGE_EXECUTION_PLAN["dividend_growth"] == (
        "src.dividend_bot.dividend_growth_engine",
        "build_dividend_growth_report",
    )
    assert STAGE_EXECUTION_PLAN["dividend_safety"] == (
        "src.dividend_bot.dividend_safety_engine",
        "build_dividend_safety_report",
    )
    assert STAGE_EXECUTION_PLAN["valuation"] == (
        "src.dividend_bot.valuation_engine",
        "build_valuation_report",
    )


def test_component_stages_are_reporting_only_by_contract():
    from src.dividend_bot import dividend_growth_engine
    from src.dividend_bot import dividend_quality_engine
    from src.dividend_bot import dividend_safety_engine
    from src.dividend_bot import valuation_engine

    for engine in (
        dividend_quality_engine,
        dividend_growth_engine,
        dividend_safety_engine,
        valuation_engine,
    ):
        assert engine.PAPER_TRADE_MODE is True
        assert engine.REPORTING_ONLY is True
        assert engine.LIVE_TRADING_ENABLED is False
        assert engine.BROKER_EXECUTION_ENABLED is False
        assert engine.ORDER_PLACEMENT_ENABLED is False
        assert engine.CAPITAL_MOVEMENT_ENABLED is False
        assert engine.AUTOMATIC_ACTIVATION_ALLOWED is False
