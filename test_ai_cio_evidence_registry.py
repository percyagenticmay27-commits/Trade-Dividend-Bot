from pathlib import Path

import ai_cio_evidence_registry as module


def sample_record(**overrides):
    payload = {
        "evidence_type": "EARNINGS",
        "title": "AMD earnings",
        "summary": "Revenue and guidance improved.",
        "source": "Company release",
        "observed_at": "2026-07-14T20:05:00Z",
        "confidence": 94.0,
        "symbol": "AMD",
        "sector": "Technology",
        "related_thesis_ids": ["T-1"],
        "related_policy_ids": ["P-1"],
        "related_market_era_ids": ["M-1"],
        "review_at": "2026-10-15",
        "metadata": {"quarter": "Q2"},
    }
    payload.update(overrides)
    return module.build_evidence_record(**payload)


def test_public_functions_exist():
    assert callable(module.build_evidence_record)
    assert callable(module.validate_evidence_record)
    assert callable(module.supersede_evidence)
    assert callable(module.build_evidence_registry)
    assert callable(module.find_evidence)
    assert callable(module.write_evidence_registry)
    assert callable(module.build_and_write_evidence_registry)


def test_paper_only_flags():
    report = module.build_evidence_registry(records=[])
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_build_record_required_fields():
    record = sample_record()
    assert record["evidence_id"].startswith("E-")
    assert record["immutable"] is True
    assert record["status"] == "ACTIVE"
    assert record["symbol"] == "AMD"
    assert record["content_hash"]


def test_symbol_is_normalized():
    assert sample_record(symbol="amd")["symbol"] == "AMD"


def test_confidence_is_clamped_high():
    assert sample_record(confidence=150)["confidence"] == 100.0


def test_confidence_is_clamped_low():
    assert sample_record(confidence=-5)["confidence"] == 0.0


def test_invalid_evidence_type_rejected():
    try:
        sample_record(evidence_type="MAGIC")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_blank_title_rejected():
    try:
        sample_record(title="")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_record_validates():
    assert module.validate_evidence_record(sample_record()) == []


def test_modified_record_fails_hash_validation():
    record = sample_record()
    record["summary"] = "Tampered"
    assert any("content_hash mismatch" in e for e in module.validate_evidence_record(record))


def test_immutable_flag_required():
    record = sample_record()
    record["immutable"] = False
    assert any("immutable" in e.lower() for e in module.validate_evidence_record(record))


def test_supersede_preserves_original_id():
    original = sample_record()
    old, new = module.supersede_evidence(
        original,
        summary="Updated guidance reduced.",
        source="Revised company filing",
        observed_at="2026-07-15T12:00:00Z",
        confidence=99,
    )
    assert old["evidence_id"] == original["evidence_id"]
    assert old["status"] == "SUPERSEDED"
    assert new["supersedes_evidence_id"] == original["evidence_id"]
    assert new["evidence_id"] != original["evidence_id"]


def test_superseding_record_is_valid():
    original = sample_record()
    old, new = module.supersede_evidence(
        original,
        summary="Updated evidence.",
        source="Updated filing",
        observed_at="2026-07-16T00:00:00Z",
        confidence=90,
    )
    assert module.validate_evidence_record(old) == []
    assert module.validate_evidence_record(new) == []


def test_invalid_previous_record_cannot_be_superseded():
    bad = sample_record()
    bad["summary"] = "Changed"
    try:
        module.supersede_evidence(bad, summary="New", source="Source", observed_at="2026-01-01", confidence=80)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_registry_counts_records():
    record = sample_record()
    report = module.build_evidence_registry(records=[record])
    assert report["record_count"] == 1
    assert report["active_record_count"] == 1
    assert report["invalid_record_count"] == 0


def test_registry_groups_by_type_symbol_and_status():
    r1 = sample_record()
    r2 = sample_record(evidence_type="NEWS", title="AMD news")
    report = module.build_evidence_registry(records=[r1, r2])
    assert report["records_by_type"]["EARNINGS"] == 1
    assert report["records_by_type"]["NEWS"] == 1
    assert report["records_by_symbol"]["AMD"] == 2
    assert report["records_by_status"]["ACTIVE"] == 2


def test_registry_average_confidence():
    r1 = sample_record(confidence=80)
    r2 = sample_record(confidence=100, title="Second")
    assert module.build_evidence_registry(records=[r1, r2])["average_active_confidence"] == 90.0


def test_invalid_record_is_excluded():
    bad = sample_record()
    bad["summary"] = "Tampered"
    report = module.build_evidence_registry(records=[bad])
    assert report["record_count"] == 0
    assert report["invalid_record_count"] == 1
    assert report["warnings"]


def test_duplicate_id_is_invalid():
    record = sample_record()
    report = module.build_evidence_registry(records=[record, dict(record)])
    assert report["record_count"] == 1
    assert report["invalid_record_count"] == 1


def test_non_mapping_record_is_invalid():
    report = module.build_evidence_registry(records=["bad"])
    assert report["invalid_record_count"] == 1


def test_orphan_evidence_warning():
    record = sample_record()
    report = module.build_evidence_registry(records=[record], decision_links=[])
    assert record["evidence_id"] in report["orphan_evidence_ids"]
    assert any("not linked" in w for w in report["warnings"])


def test_linked_evidence_is_not_orphan():
    record = sample_record()
    report = module.build_evidence_registry(records=[record], decision_links=[{"evidence_id": record["evidence_id"], "decision_id": "D1"}])
    assert report["orphan_evidence_ids"] == []


def test_find_by_symbol():
    amd = sample_record()
    nvda = sample_record(symbol="NVDA", title="NVDA earnings")
    report = module.build_evidence_registry(records=[amd, nvda])
    results = module.find_evidence(report, symbol="AMD")
    assert len(results) == 1
    assert results[0]["symbol"] == "AMD"


def test_find_by_type():
    earnings = sample_record()
    news = sample_record(evidence_type="NEWS", title="AMD news")
    report = module.build_evidence_registry(records=[earnings, news])
    assert len(module.find_evidence(report, evidence_type="NEWS")) == 1


def test_find_by_minimum_confidence():
    low = sample_record(confidence=40)
    high = sample_record(confidence=95, title="High confidence")
    report = module.build_evidence_registry(records=[low, high])
    assert len(module.find_evidence(report, minimum_confidence=90)) == 1


def test_find_defaults_to_active_status():
    record = sample_record()
    old, new = module.supersede_evidence(record, summary="Updated", source="Updated source", observed_at="2026-07-15", confidence=90)
    report = module.build_evidence_registry(records=[old, new])
    results = module.find_evidence(report)
    assert len(results) == 1
    assert results[0]["status"] == "ACTIVE"


def test_governance_locks():
    governance = module.build_evidence_registry(records=[])["governance"]
    assert governance["evidence_records_editable"] is False
    assert governance["corrections_require_superseding_record"] is True
    assert governance["original_evidence_preserved"] is True
    assert governance["automatic_policy_changes_allowed"] is False


def test_markdown_contains_summary():
    report = module.build_evidence_registry(records=[sample_record()])
    markdown = module.format_evidence_registry_markdown(report)
    assert "AI CIO Evidence Registry" in markdown
    assert "Evidence Summary" in markdown
    assert "immutable" in markdown.lower()


def test_html_contains_title():
    report = module.build_evidence_registry(records=[])
    html = module.format_evidence_registry_html(report)
    assert "<!doctype html>" in html.lower()
    assert "AI CIO Evidence Registry" in html


def test_write_outputs(tmp_path):
    record = sample_record()
    report = module.write_evidence_registry({"records": [record]}, root_path=str(tmp_path))
    assert report["record_count"] == 1
    assert (tmp_path / "evidence_registry.json").exists()
    assert (tmp_path / "evidence_registry.md").exists()
    assert (tmp_path / "evidence_registry.html").exists()


def test_custom_output_names(tmp_path):
    module.write_evidence_registry(
        {"records": []},
        root_path=str(tmp_path),
        output_files={"json": "a.json", "markdown": "b.md", "html": "c.html"},
    )
    assert (tmp_path / "a.json").exists()
    assert (tmp_path / "b.md").exists()
    assert (tmp_path / "c.html").exists()


def test_invalid_payload_rejected(tmp_path):
    try:
        module.write_evidence_registry("bad", root_path=str(tmp_path))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_nonfinite_confidence_is_sanitized():
    assert sample_record(confidence=float("inf"))["confidence"] == 0.0


def test_no_broker_or_order_execution_imports():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["import robin_stocks", "import alpaca", "submit_order(", "place_order(", "broker.login"]
    assert not any(item in source for item in forbidden)
