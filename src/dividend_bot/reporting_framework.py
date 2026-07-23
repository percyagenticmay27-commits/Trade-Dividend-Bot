"""Shared report models and deterministic renderers with strict strategy isolation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .platform_entities import ReportInstance
from .platform_foundation import JsonSerializer, PlatformSettings, PlatformValidationError

MODULE_NAME = "reporting_framework"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Strategy-isolated report modeling, rendering, and output path governance."


@dataclass(frozen=True)
class ReportSection:
    heading: str
    values: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.heading.strip():
            raise PlatformValidationError("report section heading must not be empty")


@dataclass(frozen=True)
class StrategyReportModel:
    strategy_id: str
    report_type: str
    title: str
    period_start: datetime
    period_end: datetime
    sections: tuple[ReportSection, ...]
    warnings: tuple[str, ...] = ()
    decision_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("report strategy_id must be non-empty uppercase text")
        if not self.report_type or self.report_type != self.report_type.upper():
            raise PlatformValidationError("report_type must be non-empty uppercase text")
        if not self.title.strip():
            raise PlatformValidationError("report title must not be empty")
        if self.period_start.tzinfo is None or self.period_end.tzinfo is None:
            raise PlatformValidationError("report period timestamps must be timezone-aware")
        if self.period_end < self.period_start:
            raise PlatformValidationError("report period end must not precede start")
        if not self.sections:
            raise PlatformValidationError("report must contain at least one section")
        for section in self.sections:
            section.validate()


class StrategyReportRenderer:
    """Render one strategy report at a time without combining strategy histories."""

    def __init__(self, settings: PlatformSettings | None = None) -> None:
        self._settings = settings or PlatformSettings()
        self._settings.validate()

    def output_directory(self, model: StrategyReportModel) -> Path:
        model.validate()
        return self._settings.strategy_results_path(model.strategy_id, model.report_type)

    def render_json(self, model: StrategyReportModel) -> str:
        model.validate()
        return JsonSerializer.dumps(model)

    def render_markdown(self, model: StrategyReportModel) -> str:
        model.validate()
        lines = [
            f"# {model.title}",
            "",
            f"- Strategy: {model.strategy_id}",
            f"- Report Type: {model.report_type}",
            f"- Period Start: {JsonSerializer.to_primitive(model.period_start)}",
            f"- Period End: {JsonSerializer.to_primitive(model.period_end)}",
            "",
        ]
        for section in model.sections:
            lines.extend([f"## {section.heading}", ""])
            for key, value in sorted(section.values.items()):
                lines.append(f"- {key}: {JsonSerializer.to_primitive(value)}")
            for note in section.notes:
                lines.append(f"- Note: {note}")
            lines.append("")
        if model.warnings:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in model.warnings)
            lines.append("")
        if model.decision_ids:
            lines.extend(["## Decisions", ""])
            lines.extend(f"- {decision_id}" for decision_id in model.decision_ids)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def build_report_instance(
        self,
        model: StrategyReportModel,
        *,
        identity,
        output_paths: tuple[str, ...],
    ) -> ReportInstance:
        model.validate()
        metrics: dict[str, Any] = {}
        for section in model.sections:
            for key, value in section.values.items():
                metrics[f"{section.heading}.{key}"] = value
        instance = ReportInstance(
            identity=identity,
            strategy_id=model.strategy_id,
            report_type=model.report_type,
            period_start=model.period_start,
            period_end=model.period_end,
            metrics=metrics,
            decision_ids=(),
            output_paths=output_paths,
        )
        instance.validate()
        return instance


def ensure_single_strategy(models: tuple[StrategyReportModel, ...]) -> str:
    if not models:
        raise PlatformValidationError("at least one report model is required")
    strategy_ids = {model.strategy_id for model in models}
    if len(strategy_ids) != 1:
        raise PlatformValidationError("reports from different strategies must not be combined")
    return next(iter(strategy_ids))
