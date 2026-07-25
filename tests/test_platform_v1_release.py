from pathlib import Path

from src.dividend_bot import platform_v1_release as release


FIXED_TIME = "2026-07-25T20:00:00Z"


def create_required_files(root: Path) -> None:
    for name in release.REQUIRED_RELEASE_FILES:
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


def test_missing_files_block_release(tmp_path):
    report = release.validate_release_files(tmp_path)
    assert report["status"] == "NOT_READY"
    assert report["missing_files"]


def test_empty_files_block_release(tmp_path):
    create_required_files(tmp_path)
    target = tmp_path / release.REQUIRED_RELEASE_FILES[0]
    target.write_text("", encoding="utf-8")
    report = release.validate_release_files(tmp_path)
    assert report["status"] == "NOT_READY"
    assert release.REQUIRED_RELEASE_FILES[0] in report["empty_files"]


def test_ready_files_pass(tmp_path):
    create_required_files(tmp_path)
    report = release.validate_release_files(tmp_path)
    assert report["status"] == "READY"
    assert report["missing_files"] == []
    assert report["empty_files"] == []


def test_release_ready_requires_all_gates(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=321,
        generated_at_utc=FIXED_TIME,
    )
    assert manifest["status"] == "RELEASE_READY"
    assert manifest["generated_at_utc"] == FIXED_TIME


def test_rejected_acceptance_blocks_release(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(
        tmp_path,
        acceptance_status="REJECTED",
        cloud_status="HEALTHY",
        combined_test_total=321,
    )
    assert manifest["status"] == "RELEASE_BLOCKED"


def test_degraded_cloud_blocks_release(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="DEGRADED",
        combined_test_total=321,
    )
    assert manifest["status"] == "RELEASE_BLOCKED"


def test_zero_tests_block_release(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=0,
    )
    assert manifest["status"] == "RELEASE_BLOCKED"


def test_governance_denies_execution_authority(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=321,
    )
    governance = manifest["governance"]
    assert governance["order_execution_allowed"] is False
    assert governance["brokerage_communication_allowed"] is False
    assert governance["capital_movement_allowed"] is False
    assert governance["automatic_policy_changes_allowed"] is False
    assert governance["investor_approval_required"] is True


def test_deferred_scope_is_preserved(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=321,
    )
    assert manifest["deferred_scope"] == ["Swing", "Options", "Futures"]


def test_json_and_markdown_outputs(tmp_path):
    create_required_files(tmp_path)
    manifest = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=321,
        generated_at_utc=FIXED_TIME,
    )
    json_path = tmp_path / "results/platform_v1_release.json"
    md_path = tmp_path / "results/platform_v1_release.md"
    assert Path(release.write_release_manifest(manifest, json_path)).is_file()
    assert Path(release.write_release_markdown(manifest, md_path)).is_file()
    text = md_path.read_text(encoding="utf-8")
    assert "RELEASE_READY" in text
    assert "dividend-platform-v1.0.0" in text
    assert "No Robinhood execution" in text


def test_identical_inputs_are_deterministic(tmp_path):
    create_required_files(tmp_path)
    first = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=321,
        generated_at_utc=FIXED_TIME,
    )
    second = release.build_release_manifest(
        tmp_path,
        acceptance_status="ACCEPTED",
        cloud_status="HEALTHY",
        combined_test_total=321,
        generated_at_utc=FIXED_TIME,
    )
    assert first == second
