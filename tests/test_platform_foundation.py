from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from dividend_bot.platform_foundation import (
    DEFAULT_PLATFORM_SETTINGS,
    IdentifierFactory,
    IdentifierKind,
    JsonSerializer,
    ModuleVersion,
    PlatformSettings,
    PlatformValidationError,
    VersionRegistry,
)


def test_default_settings_are_paper_only() -> None:
    DEFAULT_PLATFORM_SETTINGS.validate()
    assert DEFAULT_PLATFORM_SETTINGS.paper_trade_mode is True
    assert DEFAULT_PLATFORM_SETTINGS.live_trading_enabled is False
    assert DEFAULT_PLATFORM_SETTINGS.broker_execution_enabled is False


@pytest.mark.parametrize(
    "settings",
    [
        PlatformSettings(paper_trade_mode=False),
        PlatformSettings(live_trading_enabled=True),
        PlatformSettings(broker_execution_enabled=True),
    ],
)
def test_invalid_execution_settings_are_rejected(settings: PlatformSettings) -> None:
    with pytest.raises(PlatformValidationError):
        settings.validate()


def test_strategy_results_paths_are_isolated() -> None:
    settings = PlatformSettings(results_root=Path("results"))
    assert settings.strategy_results_path("Dividend", "Weekly") == Path(
        "results/dividend/weekly"
    )
    assert settings.strategy_results_path("Swing", "Weekly") == Path(
        "results/swing/weekly"
    )


def test_internal_identifier_is_uuid() -> None:
    assert isinstance(IdentifierFactory.new_internal_id(), UUID)


def test_public_identifier_format_with_explicit_sequence() -> None:
    assert (
        IdentifierFactory.new_public_id(
            IdentifierKind.DECISION,
            year=2026,
            sequence=12,
        )
        == "DEC-2026-000012"
    )


def test_invalid_public_identifier_values_are_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        IdentifierFactory.new_public_id("bad prefix!", year=2026, sequence=1)
    with pytest.raises(PlatformValidationError):
        IdentifierFactory.new_public_id("DEC", year=1999, sequence=1)
    with pytest.raises(PlatformValidationError):
        IdentifierFactory.new_public_id("DEC", year=2026, sequence=0)


def test_version_registry_rejects_conflicts() -> None:
    registry = VersionRegistry()
    registry.register(ModuleVersion("example_module", "1.0.0", "first"))
    registry.register(ModuleVersion("example_module", "1.0.0", "first"))

    with pytest.raises(PlatformValidationError):
        registry.register(ModuleVersion("example_module", "1.1.0", "changed"))


def test_version_registry_requires_valid_names_and_versions() -> None:
    registry = VersionRegistry()
    with pytest.raises(PlatformValidationError):
        registry.register(ModuleVersion("Bad-Name", "1.0.0"))
    with pytest.raises(PlatformValidationError):
        registry.register(ModuleVersion("good_name", "1.0"))


@dataclass(frozen=True)
class ExampleRecord:
    identifier: UUID
    generated_at: datetime
    output_path: Path
    strategy: IdentifierKind


def test_json_serializer_is_deterministic_and_platform_aware() -> None:
    record = ExampleRecord(
        identifier=UUID("00000000-0000-0000-0000-000000000001"),
        generated_at=datetime(2026, 7, 22, 12, 30, tzinfo=timezone.utc),
        output_path=Path("results/dividend/weekly"),
        strategy=IdentifierKind.STRATEGY,
    )

    payload = JsonSerializer.dumps(record)

    assert '"generated_at": "2026-07-22T12:30:00Z"' in payload
    assert '"identifier": "00000000-0000-0000-0000-000000000001"' in payload
    assert '"output_path": "results/dividend/weekly"' in payload
    assert payload.endswith("\n")


def test_json_serializer_supports_date_only_values() -> None:
    payload = JsonSerializer.dumps({"run_date": date(2026, 7, 24)})
    assert '"run_date": "2026-07-24"' in payload


def test_json_serializer_rejects_naive_datetime() -> None:
    with pytest.raises(PlatformValidationError):
        JsonSerializer.dumps({"generated_at": datetime(2026, 7, 22, 12, 30)})
