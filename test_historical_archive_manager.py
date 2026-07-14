import json
import zipfile
from datetime import date
from pathlib import Path

import historical_archive_manager as module


def make_record(path: Path, symbol="AMD", record_date="2025-06-01", **extra):
    payload = {"symbol": symbol, "record_date": record_date, **extra}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def make_archive(tmp_path: Path, year: int, symbol="AMD", era="AI Expansion"):
    source = make_record(tmp_path / f"{symbol}_{year}.json", symbol=symbol, record_date=f"{year}-06-01")
    archive = tmp_path / f"{year}.zip"
    module.create_annual_archive([source], archive, archive_year=year, market_era={"name": era})
    return archive


def test_public_functions_exist():
    for name in (
        "split_active_and_archivable", "build_archive_manifest", "create_annual_archive",
        "verify_archive_integrity", "build_historical_evidence_index", "plan_retention",
        "retrieve_symbol_history", "build_archive_heat_map", "build_historical_archive_report",
        "format_historical_archive_markdown", "format_historical_archive_html",
        "write_historical_archive_report", "build_and_write_historical_archive_report",
    ):
        assert callable(getattr(module, name))


def test_paper_only_flags():
    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False


def test_split_active_and_archivable(tmp_path):
    old = make_record(tmp_path / "old.json", record_date="2024-01-01")
    new = make_record(tmp_path / "new.json", record_date="2026-06-01")
    result = module.split_active_and_archivable([old, new], as_of_date=date(2026, 7, 14))
    assert str(old) in result["archivable"]
    assert str(new) in result["active"]


def test_invalid_active_days_rejected():
    try:
        module.split_active_and_archivable([], active_days=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_manifest_generation(tmp_path):
    record = make_record(tmp_path / "a.json", policy_version="1.2")
    manifest = module.build_archive_manifest([record], archive_year=2025, market_era={"name": "AI Era"})
    assert manifest["file_count"] == 1
    assert manifest["symbols"] == ["AMD"]
    assert manifest["policy_versions"] == ["1.2"]


def test_archive_creation_contains_manifest(tmp_path):
    archive = make_archive(tmp_path, 2025)
    with zipfile.ZipFile(archive) as zf:
        assert "manifest.json" in zf.namelist()


def test_archive_integrity_passes(tmp_path):
    result = module.verify_archive_integrity(make_archive(tmp_path, 2025))
    assert result["healthy"] is True
    assert result["errors"] == []


def test_missing_archive_fails_integrity(tmp_path):
    result = module.verify_archive_integrity(tmp_path / "missing.zip")
    assert result["healthy"] is False


def test_bad_zip_fails_integrity(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_text("not a zip", encoding="utf-8")
    assert module.verify_archive_integrity(bad)["healthy"] is False


def test_missing_manifest_detected(tmp_path):
    archive = tmp_path / "plain.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("x.txt", "hello")
    result = module.verify_archive_integrity(archive)
    assert result["healthy"] is False
    assert any("manifest" in err for err in result["errors"])


def test_evidence_index_symbols_and_eras(tmp_path):
    a = make_archive(tmp_path, 2025, "AMD", "AI Expansion")
    b = make_archive(tmp_path, 2026, "NVDA", "AI Expansion")
    index = module.build_historical_evidence_index([a, b])
    assert index["symbols"]["AMD"] == [2025]
    assert index["market_eras"]["AI Expansion"] == [2025, 2026]


def test_retention_plan_keeps_five(tmp_path):
    paths = [tmp_path / f"{year}.zip" for year in range(2020, 2027)]
    result = module.plan_retention(paths, retention_years=5)
    assert len(result["keep"]) == 5
    assert len(result["deletion_requires_investor_approval"]) == 2


def test_invalid_retention_rejected():
    try:
        module.plan_retention([], retention_years=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_multi_year_retrieval(tmp_path):
    archives = [make_archive(tmp_path, year) for year in (2025, 2026, 2027)]
    result = module.retrieve_symbol_history(archives, symbol="AMD", years=[2025, 2026, 2027], requester="Stock Memory", reason="Trend review")
    assert len(result["records"]) == 3
    assert result["access_log_entry"]["temporary_workspace_removed"] is True


def test_retrieval_preserves_original_archives(tmp_path):
    archives = [make_archive(tmp_path, 2025)]
    before = archives[0].read_bytes()
    result = module.retrieve_symbol_history(archives, symbol="AMD", years=[2025], requester="Test", reason="Read only")
    assert archives[0].read_bytes() == before
    assert result["access_log_entry"]["original_archives_modified"] is False


def test_retrieval_logs_access(tmp_path):
    archive = make_archive(tmp_path, 2025)
    log = tmp_path / "access.json"
    module.retrieve_symbol_history([archive], symbol="AMD", years=[2025], requester="Memory", reason="Audit", access_log_path=log)
    rows = json.loads(log.read_text(encoding="utf-8"))
    assert rows[0]["symbol"] == "AMD"
    assert rows[0]["integrity_verified"] is True


def test_retrieval_requires_symbol(tmp_path):
    try:
        module.retrieve_symbol_history([], symbol="", years=[2025], requester="X", reason="Y")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_retrieval_max_three_years(tmp_path):
    try:
        module.retrieve_symbol_history([], symbol="AMD", years=[2022, 2023, 2024, 2025], requester="X", reason="Y")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_nonmatching_symbol_returns_empty(tmp_path):
    archive = make_archive(tmp_path, 2025, symbol="AMD")
    result = module.retrieve_symbol_history([archive], symbol="NVDA", years=[2025], requester="X", reason="Y")
    assert result["records"] == []


def test_heat_map_counts_accesses():
    log = [
        {"archives_accessed": ["2025.zip"], "reason": "Thesis"},
        {"archives_accessed": ["2025.zip", "2026.zip"], "reason": "Thesis"},
    ]
    heat = module.build_archive_heat_map(log)
    assert heat[0]["archive"] == "2025.zip"
    assert heat[0]["access_count"] == 2


def test_empty_report_is_valid_with_warning():
    report = module.build_historical_archive_report()
    assert report["archive_health_percent"] == 100.0
    assert report["warnings"]
    assert report["errors"] == []


def test_populated_report_health(tmp_path):
    report = module.build_historical_archive_report(archive_paths=[make_archive(tmp_path, 2025)])
    assert report["archive_count"] == 1
    assert report["healthy_archive_count"] == 1


def test_governance_rules():
    governance = module.build_historical_archive_report()["governance"]
    assert governance["deletion_requires_investor_approval"] is True
    assert governance["read_only_retrieval_modifies_archives"] is False


def test_markdown_contains_sections():
    markdown = module.format_historical_archive_markdown(module.build_historical_archive_report())
    assert "Executive Summary" in markdown
    assert "Archive Heat Map" in markdown
    assert "Paper-Only Safety" in markdown


def test_html_contains_title():
    output = module.format_historical_archive_html(module.build_historical_archive_report())
    assert "<!doctype html>" in output.lower()
    assert "Historical Archive Manager" in output


def test_write_outputs(tmp_path):
    report = module.write_historical_archive_report({"archive_paths": [], "access_log": []}, root_path=str(tmp_path))
    assert report["module_name"] == module.MODULE_NAME
    assert (tmp_path / "archive_manager.json").exists()
    assert (tmp_path / "archive_manager.md").exists()
    assert (tmp_path / "archive_manager.html").exists()


def test_invalid_payload_rejected(tmp_path):
    try:
        module.write_historical_archive_report("invalid", root_path=str(tmp_path))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_custom_output_names(tmp_path):
    module.write_historical_archive_report({}, root_path=str(tmp_path), output_files={"json": "custom.json"})
    assert (tmp_path / "custom.json").exists()


def test_no_broker_or_order_execution_imports():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["import robin_stocks", "import alpaca", "submit_order(", "place_order(", "broker.login"]
    assert not any(item in source for item in forbidden)
