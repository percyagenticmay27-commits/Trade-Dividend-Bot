from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.dividend_bot.platform_entities import new_identity
from src.dividend_bot.platform_foundation import IdentifierKind, PlatformValidationError
from src.dividend_bot.reporting_framework import (
    ReportSection,
    StrategyReportModel,
    StrategyReportRenderer,
    ensure_single_strategy,
)


def make_model(strategy_id: str = "DIVIDEND", report_type: str = "WEEKLY") -> StrategyReportModel:
    return StrategyReportModel(
        strategy_id=strategy_id,
        report_type=report_type,
        title=f"{strategy_id.title()} {report_type.title()} Report",
        period_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 7, 7, tzinfo=timezone.utc),
        sections=(
            ReportSection(
                heading="Performance",
                values={"return_pct": 3.5, "income": 125.0},
                notes=("Paper-only results",),
            ),
        ),
        warnings=("Example warning",),
        decision_ids=("DEC-2026-000001",),
    )


def test_report_model_requires_strategy_scope() -> None:
    model = make_model(strategy_id="")
    with pytest.raises(PlatformValidationError):
        model.validate()


def test_report_model_rejects_naive_timestamps() -> None:
    model = make_model()
    object.__setattr__(model, "period_start", datetime(2026, 7, 1))
    with pytest.raises(PlatformValidationError):
        model.validate()


def test_output_directory_is_strategy_isolated() -> None:
    renderer = StrategyReportRenderer()
    assert renderer.output_directory(make_model()).as_posix() == "results/dividend/weekly"
    assert renderer.output_directory(make_model("SWING")).as_posix() == "results/swing/weekly"


def test_json_rendering_is_deterministic() -> None:
    renderer = StrategyReportRenderer()
    model = make_model()
    assert renderer.render_json(model) == renderer.render_json(model)
    assert '"strategy_id": "DIVIDEND"' in renderer.render_json(model)


def test_markdown_contains_strategy_and_period() -> None:
    rendered = StrategyReportRenderer().render_markdown(make_model())
    assert "Strategy: DIVIDEND" in rendered
    assert "Report Type: WEEKLY" in rendered
    assert "## Performance" in rendered
    assert "DEC-2026-000001" in rendered


def test_mixed_strategy_models_are_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        ensure_single_strategy((make_model("DIVIDEND"), make_model("SWING")))


def test_same_strategy_models_are_accepted() -> None:
    assert ensure_single_strategy((make_model(), make_model(report_type="MONTHLY"))) == "DIVIDEND"


def test_empty_report_collection_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        ensure_single_strategy(())


def test_build_report_instance_preserves_strategy_scope() -> None:
    renderer = StrategyReportRenderer()
    instance = renderer.build_report_instance(
        make_model(),
        identity=new_identity(IdentifierKind.REPORT),
        output_paths=("results/dividend/weekly/report.json",),
    )
    assert instance.strategy_id == "DIVIDEND"
    assert instance.report_type == "WEEKLY"
    assert instance.output_paths == ("results/dividend/weekly/report.json",)


def test_report_section_heading_is_required() -> None:
    with pytest.raises(PlatformValidationError):
        ReportSection(heading="").validate()
