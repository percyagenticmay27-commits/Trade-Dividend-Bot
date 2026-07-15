from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

import ai_cio_decision_record as mod


def make_record(**overrides):
    data = dict(
        originating_module="watchlist_engine",
        decision_type="WATCHLIST_ADMISSION",
        title="Promote ABC to watchlist",
        summary="ABC satisfied current evidence gates.",
        classification="SIGNIFICANT",
        status="APPROVED",
        symbol="abc",
        evidence_ids=["E-1", "E-2"],
        rationale=["Strong fundamentals", "Improving outlook"],
        risks=["Earnings in 20 days"],
        confidence_score=91.25,
        governance_status="PASS",
        final_outcome="NOT_APPLICABLE",
    )
    data.update(overrides)
    return mod.build_decision_record(**data)


def test_safety_constants():
    assert mod.PAPER_TRADE_MODE is True
    assert mod.LIVE_TRADING_ENABLED is False
    assert mod.BROKER_EXECUTION_ENABLED is False


def test_build_record():
    record = make_record()
    assert record.symbol == "ABC"
    assert record.decision_id.startswith("DEC-")
    assert record.record_hash


def test_record_is_frozen():
    record = make_record()
    with pytest.raises(FrozenInstanceError):
        record.title = "Changed"


def test_required_originating_module():
    with pytest.raises(ValueError):
        make_record(originating_module="")


def test_required_title():
    with pytest.raises(ValueError):
        make_record(title="")


def test_required_summary():
    with pytest.raises(ValueError):
        make_record(summary="")


def test_invalid_decision_type():
    with pytest.raises(ValueError):
        make_record(decision_type="BUY_NOW")


def test_invalid_classification():
    with pytest.raises(ValueError):
        make_record(classification="URGENT")


def test_invalid_status():
    with pytest.raises(ValueError):
        make_record(status="DONE")


def test_invalid_governance_status():
    with pytest.raises(ValueError):
        make_record(governance_status="OK")


def test_invalid_outcome():
    with pytest.raises(ValueError):
        make_record(final_outcome="WIN")


def test_confidence_lower_bound():
    with pytest.raises(ValueError):
        make_record(confidence_score=-1)


def test_confidence_upper_bound():
    with pytest.raises(ValueError):
        make_record(confidence_score=101)


def test_constitutional_requires_approval():
    with pytest.raises(ValueError):
        make_record(classification="CONSTITUTIONAL", investor_approval_required=False)


def test_governance_fail_cannot_be_approved():
    with pytest.raises(ValueError):
        make_record(governance_status="FAIL", status="APPROVED")


def test_lists_are_deduplicated():
    record = make_record(evidence_ids=["E-1", "E-1", "E-2"])
    assert record.evidence_ids == ("E-1", "E-2")


def test_to_dict_converts_tuples_to_lists():
    data = make_record().to_dict()
    assert isinstance(data["evidence_ids"], list)
    assert isinstance(data["rationale"], list)


def test_validate_valid_record():
    assert mod.validate_decision_record(make_record()) == []


def test_validate_detects_tampering():
    data = make_record().to_dict()
    data["summary"] = "tampered"
    assert "record hash mismatch" in mod.validate_decision_record(data)


def test_validate_detects_live_mode():
    data = make_record().to_dict()
    data["live_trading_enabled"] = True
    errors = mod.validate_decision_record(data)
    assert "live_trading_enabled must be False" in errors


def test_validate_detects_broker_execution():
    data = make_record().to_dict()
    data["broker_execution_enabled"] = True
    errors = mod.validate_decision_record(data)
    assert "broker_execution_enabled must be False" in errors


def test_build_register_counts():
    first = make_record()
    second = make_record(
        decision_type="POLICY_PROPOSAL",
        classification="CONSTITUTIONAL",
        status="UNDER_REVIEW",
        title="Policy proposal",
        symbol="",
        governance_status="PENDING",
        investor_approval_required=True,
        investor_action="REVIEW",
        final_outcome="PENDING",
    )
    report = mod.build_decision_register([first, second])
    assert report["record_count"] == 2
    assert report["approval_required_count"] == 1
    assert report["open_decision_count"] == 1


def test_register_detects_duplicate_id():
    record = make_record()
    report = mod.build_decision_register([record, record])
    assert report["record_count"] == 1
    assert report["invalid_record_count"] == 1
    assert "duplicate decision_id" in report["invalid_records"][0]["errors"]


def test_register_detects_invalid_mapping():
    report = mod.build_decision_register([{"decision_id": "BAD"}])
    assert report["record_count"] == 0
    assert report["invalid_record_count"] == 1


def test_register_sorting_newest_first():
    older = make_record(decision_id="DEC-OLD", timestamp="2026-01-01T00:00:00Z")
    newer = make_record(decision_id="DEC-NEW", timestamp="2026-02-01T00:00:00Z")
    report = mod.build_decision_register([older, newer])
    assert report["records"][0]["decision_id"] == "DEC-NEW"


def test_markdown_contains_governance_data():
    report = mod.build_decision_register([make_record()])
    text = mod.render_markdown(report)
    assert "# AI CIO Decision Register" in text
    assert "WATCHLIST_ADMISSION" in text
    assert "Paper-only" in text


def test_html_contains_more_details():
    report = mod.build_decision_register([make_record()])
    text = mod.render_html(report)
    assert "<!doctype html>" in text
    assert "More..." in text
    assert "cannot place orders" in text


def test_write_outputs(tmp_path):
    report = mod.build_decision_register([make_record()])
    paths = mod.write_decision_register(report, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    assert Path(paths["html"]).exists()


def test_written_json_is_valid(tmp_path):
    report = mod.build_decision_register([make_record()])
    paths = mod.write_decision_register(report, tmp_path)
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["record_count"] == 1


def test_build_and_write(tmp_path):
    report, paths = mod.build_and_write_decision_register([make_record()], tmp_path, "decisions")
    assert report["record_count"] == 1
    assert Path(paths["html"]).name == "decisions.html"


def test_superseding_decision_link():
    record = make_record(supersedes_decision_id="DEC-PRIOR")
    assert record.supersedes_decision_id == "DEC-PRIOR"


def test_related_records_and_reports():
    record = make_record(
        related_decision_ids=["DEC-A", "DEC-B"],
        related_reports=["weekly_report.json", "risk_report.json"],
    )
    assert record.related_decision_ids == ("DEC-A", "DEC-B")
    assert "weekly_report.json" in record.related_reports


def test_underlying_symbol_normalized():
    record = make_record(underlying_symbol="amd")
    assert record.underlying_symbol == "AMD"


def test_sample_records_build():
    records = mod._sample()
    assert len(records) == 2
    assert any(record.investor_approval_required for record in records)
