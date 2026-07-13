from pathlib import Path

import market_intelligence_center as module


def sample_payload():
    return {
        "market_regime": {"label": "BULL", "score": 60},
        "breadth": {"breadth_score": 40, "advancing_percent": 62, "new_highs": 80, "new_lows": 20},
        "volatility": {"percentile": 35, "trend": "STABLE"},
        "macro_signals": [{"name": "Liquidity", "score": 30}, {"name": "Rates", "score": -10}],
        "news_items": [{"headline": "Constructive market news", "sentiment_score": 50, "confidence": 90, "relevance": 90, "freshness": 100}],
        "sector_evidence": [
            {"sector": "Technology", "strength_score": 70, "momentum_score": 65, "news_score": 55, "regime_support_score": 60},
            {"sector": "Healthcare", "strength_score": 45, "momentum_score": 35, "news_score": 20, "regime_support_score": 30},
        ],
        "portfolio_exposures": [{"allocation_id": "AMDW + PLTU", "sector_context": "Technology", "allocation_percent": 40}],
    }


def build(**overrides):
    payload = sample_payload()
    payload.update(overrides)
    return module.build_market_intelligence_center(**payload)


def test_public_functions_exist():
    assert callable(module.build_market_intelligence_center)
    assert callable(module.format_market_intelligence_markdown)
    assert callable(module.format_market_intelligence_html)
    assert callable(module.write_market_intelligence_center)
    assert callable(module.build_and_write_market_intelligence_center)


def test_paper_only_flags():
    report = build()
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_overall_score_is_bounded():
    report = build()
    assert -100 <= report["overall_market_intelligence_score"] <= 100


def test_regime_is_preserved():
    report = build()
    assert report["market_regime"]["label"] == "BULL"
    assert report["market_regime"]["score"] == 60


def test_breadth_uses_advancers_and_highs_lows():
    report = build()
    assert report["market_breadth"]["score"] > 0
    assert report["market_breadth"]["label"] in {"SUPPORTIVE", "STRONGLY_SUPPORTIVE"}


def test_volatility_is_normalized():
    report = build()
    assert report["volatility"]["percentile"] == 35
    assert report["volatility"]["trend"] == "STABLE"


def test_macro_signals_are_aggregated():
    report = build()
    assert report["macro_context"]["score"] == 10
    assert len(report["macro_context"]["signals"]) == 2


def test_news_is_weighted_and_preserved():
    report = build()
    assert report["news_sentiment"]["score"] == 50
    assert report["news_sentiment"]["items"][0]["headline"] == "Constructive market news"


def test_sector_context_is_ranked():
    report = build()
    assert report["sector_context"][0]["sector"] == "TECHNOLOGY"
    assert report["sector_context"][0]["context_score"] > report["sector_context"][1]["context_score"]


def test_sector_context_has_no_allocation_authority():
    report = build()
    assert report["portfolio_implications"]["allocation_authority"] is False
    assert all(item["allocation_authority"] is False for item in report["sector_context"])


def test_commentary_explains_no_sector_bias():
    commentary = build()["ai_cio_commentary"].lower()
    assert "sector" in commentary
    assert "independently earn capital" in commentary


def test_missing_regime_and_news_create_warnings():
    report = module.build_market_intelligence_center()
    assert len(report["warnings"]) >= 2
    assert report["errors"] == []


def test_every_metric_has_explanation():
    report = build()
    for detail in report["details"].values():
        assert detail["definition"]
        assert detail["calculation"]
        assert detail["why_it_matters"]


def test_markdown_contains_full_sections():
    markdown = module.format_market_intelligence_markdown(build())
    assert "Market Intelligence Center" in markdown
    assert "Executive Summary" in markdown
    assert "Sector Context" in markdown
    assert "AI CIO Commentary" in markdown
    assert "Metric Reference" in markdown
    assert "Paper-Only Safety" in markdown


def test_html_and_files_are_created(tmp_path):
    report = module.write_market_intelligence_center(sample_payload(), root_path=str(tmp_path))
    assert report["module_name"] == module.MODULE_NAME
    assert (tmp_path / "market_intelligence_center.json").exists()
    assert (tmp_path / "market_intelligence_center.md").exists()
    html_path = tmp_path / "market_intelligence_center.html"
    assert html_path.exists()
    assert "Market Intelligence Center" in html_path.read_text(encoding="utf-8")


def test_nonfinite_values_are_sanitized():
    report = module.build_market_intelligence_center(
        market_regime={"score": float("inf")},
        breadth={"breadth_score": float("nan")},
        volatility={"percentile": float("inf")},
    )
    assert -100 <= report["overall_market_intelligence_score"] <= 100


def test_no_restricted_execution_calls():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["import robin_stocks", "import alpaca", "submit_order(", "place_order(", "broker.login"]
    assert not any(item in source for item in forbidden)
