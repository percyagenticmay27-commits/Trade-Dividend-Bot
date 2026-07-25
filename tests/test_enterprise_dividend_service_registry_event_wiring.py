from pathlib import Path

import pytest

from src.dividend_bot.enterprise_dividend_service_registry_event_wiring import (
    ADVISORY_ONLY,
    BROKER_EXECUTION_ENABLED,
    EVENT_ROUTING_ONLY,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    REGISTRY_ONLY,
    SERVICE_ORDER,
    build_and_write_service_registry,
    build_service_registry,
    default_dividend_services,
    render_service_registry_markdown,
    route_dividend_event,
    write_service_registry,
)

FIXED_TIME = "2026-07-25T16:00:00Z"


def test_safety_constants_are_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert ADVISORY_ONLY is True
    assert REGISTRY_ONLY is True
    assert EVENT_ROUTING_ONLY is True


def test_default_services_follow_platform_order():
    services = default_dividend_services()
    assert [item["service_name"] for item in services] == list(SERVICE_ORDER)
    assert [item["sequence"] for item in services] == list(range(1, len(SERVICE_ORDER) + 1))


def test_default_first_service_has_cycle_subscription():
    first = default_dividend_services()[0]
    assert first["subscriptions"] == ["DIVIDEND_CYCLE_REQUESTED"]
    assert first["dependencies"] == []


def test_default_services_chain_dependencies_and_events():
    services = default_dividend_services()
    for index in range(1, len(services)):
        assert services[index]["dependencies"] == [services[index - 1]["service_name"]]
        assert services[index]["subscriptions"] == services[index - 1]["publications"]


def test_empty_custom_registry_is_valid():
    registry = build_service_registry(services=[], generated_at_utc=FIXED_TIME)
    assert registry["summary"]["service_count"] == 0
    assert registry["warnings"] == []


def test_default_registry_contains_all_services():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    assert registry["summary"]["service_count"] == len(SERVICE_ORDER)
    assert registry["summary"]["enabled_count"] == len(SERVICE_ORDER)


def test_default_registry_has_no_warnings():
    assert build_service_registry(generated_at_utc=FIXED_TIME)["warnings"] == []


def test_duplicate_services_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        build_service_registry(
            services=[{"service_name": "INCOME"}, {"service_name": "INCOME"}],
            generated_at_utc=FIXED_TIME,
        )


def test_unknown_service_is_rejected():
    with pytest.raises(ValueError, match="Unsupported Dividend service"):
        build_service_registry(services=[{"service_name": "BROKER"}], generated_at_utc=FIXED_TIME)


def test_unknown_dependency_is_rejected():
    with pytest.raises(ValueError, match="Unsupported dependencies"):
        build_service_registry(
            services=[{"service_name": "INCOME", "dependencies": ["UNKNOWN"]}],
            generated_at_utc=FIXED_TIME,
        )


def test_forward_dependency_is_rejected():
    with pytest.raises(ValueError, match="forward dependency"):
        build_service_registry(
            services=[{"service_name": "INCOME", "dependencies": ["FORECAST"]}],
            generated_at_utc=FIXED_TIME,
        )


def test_unknown_status_is_rejected():
    with pytest.raises(ValueError, match="Unsupported service status"):
        build_service_registry(
            services=[{"service_name": "INCOME", "status": "LIVE_TRADING"}],
            generated_at_utc=FIXED_TIME,
        )


def test_custom_services_are_sorted():
    registry = build_service_registry(
        services=[{"service_name": "FORECAST"}, {"service_name": "INCOME"}],
        generated_at_utc=FIXED_TIME,
    )
    assert [item["service_name"] for item in registry["services"]] == ["INCOME", "FORECAST"]


def test_disabled_service_is_counted():
    registry = build_service_registry(
        services=[{"service_name": "INCOME", "enabled": False}],
        generated_at_utc=FIXED_TIME,
    )
    assert registry["summary"]["disabled_count"] == 1


def test_missing_event_publisher_creates_warning():
    registry = build_service_registry(
        services=[{"service_name": "INCOME", "subscriptions": ["MISSING_EVENT"]}],
        generated_at_utc=FIXED_TIME,
    )
    assert registry["summary"]["warning_count"] == 1


def test_fixed_registry_is_deterministic():
    first = build_service_registry(generated_at_utc=FIXED_TIME)
    second = build_service_registry(generated_at_utc=FIXED_TIME)
    assert first == second


def test_registry_hash_changes_with_configuration():
    first = build_service_registry(generated_at_utc=FIXED_TIME)
    second = build_service_registry(
        services=[{"service_name": "LIFECYCLE"}], generated_at_utc=FIXED_TIME
    )
    assert first["registry_hash"] != second["registry_hash"]


def test_route_event_to_registered_subscriber():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    event = route_dividend_event(
        registry=registry,
        event_type="DIVIDEND_LIFECYCLE_UPDATED",
        source_service="LIFECYCLE",
        payload={"symbol": "ABC"},
        correlation_id="cycle-1",
        occurred_at_utc=FIXED_TIME,
    )
    assert event["routing_status"] == "ROUTED"
    assert event["subscriber_services"] == ["INCOME"]


def test_event_identity_is_deterministic():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    kwargs = dict(
        registry=registry,
        event_type="DIVIDEND_LIFECYCLE_UPDATED",
        source_service="LIFECYCLE",
        payload={"b": 2, "a": 1},
        correlation_id="cycle-1",
        occurred_at_utc=FIXED_TIME,
    )
    assert route_dividend_event(**kwargs)["event_id"] == route_dividend_event(**kwargs)["event_id"]


def test_payload_change_changes_event_identity():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    first = route_dividend_event(
        registry=registry, event_type="DIVIDEND_LIFECYCLE_UPDATED",
        source_service="LIFECYCLE", payload={"value": 1}, correlation_id="cycle-1",
        occurred_at_utc=FIXED_TIME,
    )
    second = route_dividend_event(
        registry=registry, event_type="DIVIDEND_LIFECYCLE_UPDATED",
        source_service="LIFECYCLE", payload={"value": 2}, correlation_id="cycle-1",
        occurred_at_utc=FIXED_TIME,
    )
    assert first["event_id"] != second["event_id"]


def test_duplicate_event_is_ignored():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    first = route_dividend_event(
        registry=registry, event_type="DIVIDEND_LIFECYCLE_UPDATED",
        source_service="LIFECYCLE", payload={}, correlation_id="cycle-1",
        occurred_at_utc=FIXED_TIME,
    )
    duplicate = route_dividend_event(
        registry=registry, event_type="DIVIDEND_LIFECYCLE_UPDATED",
        source_service="LIFECYCLE", payload={}, correlation_id="cycle-1",
        occurred_at_utc=FIXED_TIME, processed_event_ids=[first["event_id"]],
    )
    assert duplicate["duplicate"] is True
    assert duplicate["routing_status"] == "DUPLICATE_IGNORED"
    assert duplicate["subscriber_services"] == []


def test_unregistered_source_is_rejected():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    with pytest.raises(ValueError, match="not registered"):
        route_dividend_event(
            registry=registry, event_type="EVENT", source_service="UNKNOWN",
            occurred_at_utc=FIXED_TIME,
        )


def test_unpublished_event_is_rejected():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    with pytest.raises(ValueError, match="does not publish"):
        route_dividend_event(
            registry=registry, event_type="UNSUPPORTED_EVENT", source_service="LIFECYCLE",
            occurred_at_utc=FIXED_TIME,
        )


def test_disabled_subscriber_is_not_routed():
    registry = build_service_registry(
        services=[
            {"service_name": "LIFECYCLE", "publications": ["EVENT_A"]},
            {"service_name": "INCOME", "dependencies": ["LIFECYCLE"], "subscriptions": ["EVENT_A"], "enabled": False},
        ],
        generated_at_utc=FIXED_TIME,
    )
    event = route_dividend_event(
        registry=registry, event_type="EVENT_A", source_service="LIFECYCLE",
        occurred_at_utc=FIXED_TIME,
    )
    assert event["routing_status"] == "NO_SUBSCRIBERS"


def test_governance_denies_invocation_and_execution():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    assert registry["governance"] == {
        "service_invocation_allowed": False,
        "order_execution_allowed": False,
        "capital_movement_allowed": False,
        "policy_changes_allowed": False,
    }


def test_markdown_contains_registry_and_governance():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    markdown = render_service_registry_markdown(registry)
    assert "# Enterprise Dividend Service Registry" in markdown
    assert "LIFECYCLE" in markdown
    assert "DAILY_CYCLE" in markdown
    assert "paper-only" in markdown


def test_write_outputs_json_and_markdown(tmp_path: Path):
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    paths = write_service_registry(registry, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()


def test_build_and_write_adds_output_files(tmp_path: Path):
    registry = build_and_write_service_registry(tmp_path, generated_at_utc=FIXED_TIME)
    assert set(registry["output_files"]) == {"json", "markdown"}


def test_output_metadata_is_complete():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    for key in (
        "module_name", "module_version", "schema_version", "registry_hash",
        "generated_at_utc", "paper_trade_mode", "summary", "services", "governance",
    ):
        assert key in registry
