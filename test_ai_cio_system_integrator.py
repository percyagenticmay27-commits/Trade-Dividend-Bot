from pathlib import Path

import ai_cio_system_integrator as module


def test_public_functions_exist():
    assert callable(module.build_ai_cio_system_integration)
    assert callable(module.format_ai_cio_system_integration_markdown)
    assert callable(module.format_ai_cio_system_integration_html)
    assert callable(module.write_ai_cio_system_integration)
    assert callable(module.build_and_write_ai_cio_system_integration)


def test_paper_only_flags():
    report = module.build_ai_cio_system_integration(workflow=[])
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_empty_workflow_is_ready():
    report = module.build_ai_cio_system_integration(workflow=[])
    assert report["overall_status"] == "READY_FOR_END_TO_END_QA"
    assert report["readiness_percent"] == 100.0
    assert report["workflow_module_count"] == len(module.DEFAULT_WORKFLOW)
    assert report["ready_module_count"] == len(module.DEFAULT_WORKFLOW)
    assert report["execution_results"] == []


def test_known_module_is_ready():
    report = module.build_ai_cio_system_integration(workflow=["ai_cio_system_integrator"])
    assert report["ready_module_count"] == 1
    assert report["workflow"][0]["status"] == "READY"
    assert report["workflow"][0]["paper_trade_mode"] is True


def test_missing_module_marks_incomplete():
    report = module.build_ai_cio_system_integration(workflow=["module_that_does_not_exist_123"])
    assert report["overall_status"] == "INCOMPLETE"
    assert report["missing_or_import_error_count"] == 1
    assert report["warnings"]


def test_workflow_order_is_preserved():
    report = module.build_ai_cio_system_integration(
        workflow=["ai_cio_system_integrator", "json"]
    )
    assert report["workflow"][0]["workflow_order"] == 1
    assert report["workflow"][1]["workflow_order"] == 2


def test_invalid_workflow_entry_rejected():
    try:
        module.build_ai_cio_system_integration(workflow=[""])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_structural_audit_does_not_execute_builders():
    report = module.build_ai_cio_system_integration(
        workflow=["ai_cio_system_integrator"],
        execute_available_builders=False,
    )
    assert report["execution_results"] == []
    assert any("structural readiness audit" in item for item in report["warnings"])


def test_builder_executes_only_with_payload():
    report = module.build_ai_cio_system_integration(
        workflow=["ai_cio_system_integrator"],
        module_payloads={"ai_cio_system_integrator": {"workflow": []}},
        execute_available_builders=True,
    )
    assert report["execution_results"][0]["status"] == "PASSED"
    assert report["execution_failure_count"] == 0


def test_builder_without_payload_is_skipped():
    report = module.build_ai_cio_system_integration(
        workflow=["ai_cio_system_integrator"],
        module_payloads={},
        execute_available_builders=True,
    )
    assert report["execution_results"] == []


def test_governance_is_locked():
    governance = module.build_ai_cio_system_integration(workflow=[])["governance"]
    assert governance["automatic_policy_changes_allowed"] is False
    assert governance["brokerage_execution_allowed"] is False
    assert governance["sector_allocation_entitlement"] is False
    assert governance["html_ui_modernization_deferred"] is True


def test_markdown_contains_readiness_and_workflow():
    report = module.build_ai_cio_system_integration(workflow=["ai_cio_system_integrator"])
    markdown = module.format_ai_cio_system_integration_markdown(report)
    assert "AI CIO System Integration Report" in markdown
    assert "Ordered Workflow" in markdown
    assert "Governance" in markdown
    assert "Next Phase" in markdown


def test_html_contains_report_title():
    report = module.build_ai_cio_system_integration(workflow=[])
    html = module.format_ai_cio_system_integration_html(report)
    assert "AI CIO System Integration" in html
    assert "<!doctype html>" in html.lower()


def test_write_outputs(tmp_path):
    report = module.write_ai_cio_system_integration(
        {"workflow": []}, root_path=str(tmp_path)
    )
    assert report["module_name"] == module.MODULE_NAME
    assert (tmp_path / "ai_cio_system_integration.json").exists()
    assert (tmp_path / "ai_cio_system_integration.md").exists()
    assert (tmp_path / "ai_cio_system_integration.html").exists()


def test_invalid_payload_rejected(tmp_path):
    try:
        module.write_ai_cio_system_integration("invalid", root_path=str(tmp_path))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_no_broker_or_order_execution_imports():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = [
        "import robin_stocks",
        "import alpaca",
        "submit_order(",
        "place_order(",
        "broker.login",
    ]
    assert not any(item in source for item in forbidden)
