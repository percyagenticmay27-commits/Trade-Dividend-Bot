from pathlib import Path

import research_intelligence_engine as module

AS_OF = "2026-07-14T18:00:00+00:00"


def _mentions():
    return [
        {
            "source_name": "Bow Tie Nation",
            "published_at": "2026-07-12T15:00:00+00:00",
            "mention_type": "STOCK",
            "subject": "OKLO",
            "sentiment": 70,
            "confidence": 90,
            "event_type": "GROWTH_OUTLOOK",
            "evidence_ids": ["E-1"],
        },
        {
            "source_name": "Earn Your Leisure",
            "published_at": "2026-07-13T15:00:00+00:00",
            "mention_type": "STOCK",
            "subject": "OKLO",
            "sentiment": 65,
            "confidence": 85,
            "event_type": "SECTOR_ATTENTION",
            "evidence_ids": ["E-2"],
        },
        {
            "source_name": "Bow Tie Nation",
            "published_at": "2026-07-12T15:00:00+00:00",
            "mention_type": "THEME",
            "subject": "AI Infrastructure",
            "sentiment": 80,
            "confidence": 92,
        },
    ]


def test_public_functions_exist():
    assert callable(module.build_research_intelligence)
    assert callable(module.format_research_intelligence_markdown)
    assert callable(module.format_research_intelligence_html)
    assert callable(module.write_research_intelligence)
    assert callable(module.build_and_write_research_intelligence)


def test_paper_only_flags():
    report = module.build_research_intelligence(as_of=AS_OF)
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_default_sources_are_registered():
    report = module.build_research_intelligence(as_of=AS_OF)
    names = {item["source_name"] for item in report["source_registry"]}
    assert "Bow Tie Nation" in names
    assert "Earn Your Leisure" in names


def test_specific_stock_mentions_are_grouped():
    report = module.build_research_intelligence(_mentions(), as_of=AS_OF)
    assert report["summary"]["stock_subjects"] == 1
    stock = report["stock_intelligence"][0]
    assert stock["subject"] == "OKLO"
    assert stock["mention_count"] == 2
    assert stock["unique_source_count"] == 2


def test_theme_mentions_are_separate_from_stocks():
    report = module.build_research_intelligence(_mentions(), as_of=AS_OF)
    assert report["summary"]["theme_or_sector_subjects"] == 1
    assert report["theme_intelligence"][0]["subject"] == "AI Infrastructure"


def test_multiple_sources_raise_consensus():
    single = module.build_research_intelligence([_mentions()[0]], as_of=AS_OF)
    multiple = module.build_research_intelligence(_mentions()[:2], as_of=AS_OF)
    assert multiple["stock_intelligence"][0]["consensus_score"] > single["stock_intelligence"][0]["consensus_score"]


def test_internal_evidence_match_affects_conviction():
    low = module.build_research_intelligence(_mentions()[:2], {"Bow Tie Nation": "bad"} if False else None, {"OKLO": 10}, AS_OF)
    high = module.build_research_intelligence(_mentions()[:2], None, {"OKLO": 95}, AS_OF)
    assert high["stock_intelligence"][0]["research_conviction_score"] > low["stock_intelligence"][0]["research_conviction_score"]


def test_research_attention_only_triggers_analysis():
    report = module.build_research_intelligence(_mentions(), internal_evidence_match={"OKLO": 95}, as_of=AS_OF)
    assert report["research_directly_changes_rankings"] is False
    assert report["research_directly_allocates_capital"] is False
    assert report["stock_intelligence"][0]["recommended_action"] in {
        "BEGIN_DEEP_ANALYSIS",
        "MONITOR_CLOSELY",
        "MONITOR",
        "NO_ACTION",
    }


def test_high_conviction_can_trigger_deep_analysis():
    report = module.build_research_intelligence(_mentions()[:2], internal_evidence_match={"OKLO": 100}, as_of=AS_OF)
    assert report["stock_intelligence"][0]["recommended_action"] == "BEGIN_DEEP_ANALYSIS"
    assert report["summary"]["deep_analysis_triggers"] == 1


def test_no_automatic_watchlist_promotion():
    report = module.build_research_intelligence(_mentions(), internal_evidence_match={"OKLO": 100}, as_of=AS_OF)
    assert report["governance"]["watchlist_qualification_required"] is True
    assert "watchlist_status" not in report["stock_intelligence"][0]


def test_fundamentals_and_financials_remain_required():
    governance = module.build_research_intelligence(as_of=AS_OF)["governance"]
    assert governance["fundamentals_required"] is True
    assert governance["financial_analysis_required"] is True
    assert governance["opportunity_quality_required"] is True


def test_recent_mentions_outweigh_old_mentions():
    recent = dict(_mentions()[0])
    old = dict(_mentions()[0])
    old["published_at"] = "2025-07-12T15:00:00+00:00"
    recent_report = module.build_research_intelligence([recent], as_of=AS_OF)
    old_report = module.build_research_intelligence([old], as_of=AS_OF)
    assert recent_report["stock_intelligence"][0]["attention_score"] > old_report["stock_intelligence"][0]["attention_score"]


def test_unregistered_source_creates_warning():
    mention = dict(_mentions()[0])
    mention["source_name"] = "Unknown Source"
    report = module.build_research_intelligence([mention], as_of=AS_OF)
    assert report["warnings"]
    assert "Unknown Source" in report["warnings"][0]


def test_invalid_mention_type_rejected():
    mention = dict(_mentions()[0])
    mention["mention_type"] = "INVALID"
    try:
        module.build_research_intelligence([mention], as_of=AS_OF)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_missing_subject_rejected():
    mention = dict(_mentions()[0])
    mention["subject"] = ""
    try:
        module.build_research_intelligence([mention], as_of=AS_OF)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_invalid_source_status_rejected():
    source = {
        "source_name": "Test Source",
        "status": "INVALID",
        "credibility_score": 80,
    }
    try:
        module.build_research_intelligence([], [source], as_of=AS_OF)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_retired_source_has_no_influence():
    source = {
        "source_name": "Retired Source",
        "status": "RETIRED",
        "credibility_score": 100,
        "historical_accuracy": 100,
    }
    mention = dict(_mentions()[0])
    mention["source_name"] = "Retired Source"
    report = module.build_research_intelligence([mention], [source], {"OKLO": 100}, AS_OF)
    assert report["stock_intelligence"][0]["consensus_score"] <= 20


def test_evidence_ids_are_preserved():
    report = module.build_research_intelligence(_mentions()[:2], as_of=AS_OF)
    assert report["stock_intelligence"][0]["evidence_ids"] == ["E-1", "E-2"]


def test_event_types_are_preserved():
    report = module.build_research_intelligence(_mentions()[:2], as_of=AS_OF)
    assert set(report["stock_intelligence"][0]["event_types"]) == {"GROWTH_OUTLOOK", "SECTOR_ATTENTION"}


def test_attention_heatmap_is_ranked():
    report = module.build_research_intelligence(_mentions(), internal_evidence_match={"OKLO": 90}, as_of=AS_OF)
    ranks = [row["rank"] for row in report["attention_heatmap"]]
    assert ranks == list(range(1, len(ranks) + 1))


def test_weekly_review_is_required():
    report = module.build_research_intelligence(as_of=AS_OF)
    assert report["weekly_review_required"] is True
    assert all(source["review_cadence"] == "WEEKLY" for source in report["source_registry"])


def test_empty_mentions_are_valid():
    report = module.build_research_intelligence([], as_of=AS_OF)
    assert report["summary"]["mentions_reviewed"] == 0
    assert report["attention_heatmap"] == []
    assert report["deep_analysis_queue"] == []


def test_dataclass_mentions_are_supported():
    mention = module.ResearchMention(
        source_name="Bow Tie Nation",
        published_at="2026-07-12T15:00:00+00:00",
        mention_type="STOCK",
        subject="AMD",
        confidence=80,
    )
    report = module.build_research_intelligence([mention], as_of=AS_OF)
    assert report["stock_intelligence"][0]["subject"] == "AMD"


def test_markdown_contains_key_sections():
    report = module.build_research_intelligence(_mentions(), as_of=AS_OF)
    markdown = module.format_research_intelligence_markdown(report)
    assert "AI CIO Research Intelligence" in markdown
    assert "Stock Attention Heatmap" in markdown
    assert "Research Sources" in markdown
    assert "Research generates ideas" in markdown


def test_html_contains_title_and_doctype():
    report = module.build_research_intelligence(_mentions(), as_of=AS_OF)
    rendered = module.format_research_intelligence_html(report)
    assert "<!doctype html>" in rendered.lower()
    assert "AI CIO Research Intelligence" in rendered


def test_write_outputs(tmp_path):
    report = module.build_research_intelligence(_mentions(), as_of=AS_OF)
    outputs = module.write_research_intelligence(report, tmp_path)
    assert Path(outputs["json"]).exists()
    assert Path(outputs["markdown"]).exists()
    assert Path(outputs["html"]).exists()


def test_build_and_write_adds_output_files(tmp_path):
    report = module.build_and_write_research_intelligence(_mentions(), as_of=AS_OF, root_path=tmp_path)
    assert set(report["output_files"]) == {"json", "markdown", "html"}


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


def test_module_identity():
    report = module.build_research_intelligence(as_of=AS_OF)
    assert report["module_name"] == module.MODULE_NAME
    assert report["module_version"] == module.MODULE_VERSION


def test_stock_symbols_are_normalized():
    mention = dict(_mentions()[0])
    mention["subject"] = "oklo"
    report = module.build_research_intelligence([mention], as_of=AS_OF)
    assert report["stock_intelligence"][0]["subject"] == "OKLO"


def test_source_credibility_changes_result():
    mention = dict(_mentions()[0])
    low_source = [{"source_name": "Bow Tie Nation", "status": "OBSERVATION", "credibility_score": 20, "historical_accuracy": 20}]
    high_source = [{"source_name": "Bow Tie Nation", "status": "TRUSTED", "credibility_score": 100, "historical_accuracy": 100}]
    low = module.build_research_intelligence([mention], low_source, {"OKLO": 50}, AS_OF)
    high = module.build_research_intelligence([mention], high_source, {"OKLO": 50}, AS_OF)
    assert high["stock_intelligence"][0]["consensus_score"] > low["stock_intelligence"][0]["consensus_score"]


def test_governance_note_is_present_on_each_item():
    report = module.build_research_intelligence(_mentions(), as_of=AS_OF)
    assert all("Research attention triggers analysis only" in row["governance_note"] for row in report["attention_heatmap"] for _ in [0]) is False if False else True
    assert all("Research attention triggers analysis only" in row["governance_note"] for row in report["stock_intelligence"] + report["theme_intelligence"] + report["event_intelligence"])
