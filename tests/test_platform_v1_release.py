from pathlib import Path

from src.dividend_bot import platform_v1_release as release

FIXED_TIME = "2026-07-26T14:30:00Z"


def create_required_files(root: Path, include_runtime: bool = False) -> None:
    names = list(release.REQUIRED_RELEASE_FILES)
    if include_runtime:
        names.extend(release.REQUIRED_RUNTIME_ARTIFACTS)
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("validated\n", encoding="utf-8")


def test_safety_constants_are_locked():
    assert release.PAPER_TRADE_MODE is True
    assert release.LIVE_TRADING_ENABLED is False
    assert release.BROKER_EXECUTION_ENABLED is False


def test_release_identity_is_locked():
    assert release.RELEASE_VERSION == "1.0.0"
    assert release.RELEASE_TAG == "dividend-platform-v1.0.0"


def test_final_required_files_include_cash_allocation_and_scope_freeze():
    required = set(release.REQUIRED_RELEASE_FILES)
    assert "src/dividend_bot/paper_cash_account.py" in required
    assert "src/dividend_bot/paper_capital_allocation.py" in required
    assert "src/dividend_bot/paper_capital_allocation_server.py" in required
    assert "docs/DASHBOARD_AND_WORKFLOW_SCOPE_FREEZE.md" in required
    assert "docs/PAPER_PRODUCTION_ACCEPTANCE_TEST.md" in required


def test_missing_files_block_release(tmp_path):
    assert release.validate_release_files(tmp_path)["status"] == "NOT_READY"


def test_ready_files_pass(tmp_path):
    create_required_files(tmp_path)
    assert release.validate_release_files(tmp_path)["status"] == "READY"


def test_release_ready_requires_all_gates(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=1,
        generated_at_utc=FIXED_TIME,
    )
    assert manifest["status"] == "RELEASE_READY"
    assert manifest["generated_at_utc"] == FIXED_TIME


def test_runtime_artifacts_can_be_required_for_deployment_gate(tmp_path):
    create_required_files(tmp_path)
    blocked = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=1,
        runtime_artifacts_required=True,
    )
    assert blocked["status"] == "RELEASE_BLOCKED"
    create_required_files(tmp_path, include_runtime=True)
    ready = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=1,
        runtime_artifacts_required=True,
    )
    assert ready["status"] == "RELEASE_READY"


def test_rejected_acceptance_blocks_release(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(tmp_path, acceptance_status="REJECTED", cloud_status="HEALTHY", combined_test_total=1)
    assert manifest["status"] == "RELEASE_BLOCKED"


def test_degraded_cloud_blocks_release(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(tmp_path, acceptance_status="ACCEPTED", cloud_status="DEGRADED", combined_test_total=1)
    assert manifest["status"] == "RELEASE_BLOCKED"


def test_zero_tests_block_release(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(tmp_path, acceptance_status="ACCEPTED", cloud_status="HEALTHY", combined_test_total=0)
    assert manifest["status"] == "RELEASE_BLOCKED"


def test_governance_preserves_investor_control(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(tmp_path, acceptance_status="ACCEPTED", cloud_status="HEALTHY", combined_test_total=1)
    governance = manifest["governance"]
    assert governance["order_execution_allowed"] is False
    assert governance["brokerage_communication_allowed"] is False
    assert governance["capital_movement_allowed"] is False
    assert governance["future_live_mode_investor_controlled"] is True
    assert governance["investor_approval_required"] is True


def test_json_and_markdown_outputs(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(tmp_path, acceptance_status="ACCEPTED", cloud_status="HEALTHY", combined_test_total=33, generated_at_utc=FIXED_TIME)
    json_path = tmp_path / "results/platform_v1_release.json"
    md_path = tmp_path / "results/platform_v1_release.md"
    assert release.write_release_manifest(manifest, json_path) == str(json_path)
    assert release.write_release_markdown(manifest, md_path) == str(md_path)
    assert "Investor controls any future live-mode transition" in md_path.read_text(encoding="utf-8")


def test_identical_inputs_are_deterministic_with_fixed_timestamp(tmp_path):
    create_required_files(tmp_path)
    kwargs = dict(acceptance_status="ACCEPTED", cloud_status="HEALTHY", combined_test_total=33, generated_at_utc=FIXED_TIME)
    assert release.build_release_manifest(tmp_path, **kwargs) == release.build_release_manifest(tmp_path, **kwargs)
