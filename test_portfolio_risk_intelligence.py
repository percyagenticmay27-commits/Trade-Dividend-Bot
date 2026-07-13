import json
from pathlib import Path

import pytest

import portfolio_risk_intelligence as module


def base_allocations():
    return [
        {
            "allocation_id": "AMDW + PLTU",
            "allocation_percent": 40,
            "sector_context": "Technology",
            "opportunity_style": "Growth",
            "projected_income": 1000,
            "leverage_multiplier": 1.5,
            "underlying_exposures": {"AMD": 0.5, "PLTR": 0.5},
            "earnings_days": 3,
        },
        {
            "allocation_id": "QQQI",
            "allocation_percent": 30,
            "sector_context": "Technology",
            "opportunity_style": "Income",
            "projected_income": 2000,
            "underlying_exposures": {"NVDA": 0.4, "MSFT": 0.3, "OTHER": 0.3},
        },
        {
            "allocation_id": "SGOV",
            "allocation_percent": 10,
            "sector_context": "Reserve",
            "opportunity_style": "Defensive",
            "projected_income": 200,
            "is_sgov": True,
        },
    ]


def build(**overrides):
    payload = {
        "allocations": base_allocations(),
        "correlations": [
            {"left": "AMDW + PLTU", "right": "QQQI", "correlation": 0.9}
        ],
        "decision_metrics": {
            "average_decision_stability": 85,
            "average_evidence_confidence": 94,
            "replacement_rate_percent": 8,
            "reversal_rate_percent": 2,
            "override_rate_percent": 1,
        },
        "prior_risk_history": [25, 27, 28],
    }
    payload.update(overrides)
    return module.build_portfolio_risk_intelligence(**payload)


def test_public_functions_exist():
    assert callable(module.build_portfolio_risk_intelligence)
    assert callable(module.format_portfolio_risk_markdown)
    assert callable(module.format_portfolio_risk_html)
    assert callable(module.write_portfolio_risk_intelligence)
    assert callable(module.build_and_write_portfolio_risk_intelligence)


def test_paper_only_flags():
    report = build()
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_hidden_underlying_exposure_detected():
    allocations = [
        {"allocation_id": "FUND_A", "allocation_percent": 40, "underlying_exposures": {"NVDA": 0.8}},
        {"allocation_id": "FUND_B", "allocation_percent": 35, "underlying_exposures": {"NVDA": 0.7}},
    ]
    report = module.build_portfolio_risk_intelligence(allocations=allocations)
    risk = report["risk_categories"]["underlying_exposure_risk"]
    exposures = dict(risk["exposures"])
    assert exposures["NVDA"] > 50
    assert risk["score"] >= 80


def test_sector_is_context_not_forced_allocation():
    report = build()
    assert "sector_context_risk" in report["risk_categories"]
    assert report["risk_category_weights"]["sector_context_risk"] == pytest.approx(0.08)
    commentary = report["ai_cio_commentary"].lower()
    assert "sector" in commentary
    assert "does not create forced diversification" in commentary


def test_correlation_risk_uses_pairwise_values():
    report = build()
    risk = report["risk_categories"]["correlation_risk"]
    assert risk["weighted_average_correlation"] == pytest.approx(0.9)
    assert risk["score"] > 50


def test_earnings_event_detection():
    report = build()
    risk = report["risk_categories"]["earnings_event_risk"]
    assert risk["events"][0]["allocation_id"] == "AMDW + PLTU"
    assert risk["events"][0]["days"] == 3
    assert risk["score"] > 0


def test_income_concentration():
    report = build()
    risk = report["risk_categories"]["income_concentration_risk"]
    assert risk["largest_income_share_percent"] > 60
    assert risk["score"] >= 80


def test_leverage_calculation():
    report = build()
    risk = report["risk_categories"]["leverage_risk"]
    assert risk["leveraged_allocation_percent"] == 40
    assert risk["effective_leveraged_exposure_percent"] == 60
    assert risk["score"] > 0


def test_sgov_reserve_within_range():
    report = build()
    risk = report["risk_categories"]["sgov_reserve_risk"]
    assert risk["sgov_allocation_percent"] == 10
    assert risk["status"] == "WITHIN_PREFERRED_RANGE"
    assert risk["score"] == 0


def test_decision_risk_increases_when_behavior_is_fragile():
    healthy = build()["risk_categories"]["decision_risk"]["score"]
    fragile = build(decision_metrics={
        "average_decision_stability": 40,
        "average_evidence_confidence": 50,
        "replacement_rate_percent": 50,
        "reversal_rate_percent": 35,
        "override_rate_percent": 20,
    })["risk_categories"]["decision_risk"]["score"]
    assert fragile > healthy


def test_opportunity_diversity_risk():
    report = build()
    risk = report["risk_categories"]["opportunity_diversity_risk"]
    distribution = dict(risk["distribution"])
    assert distribution["GROWTH"] == 40
    assert distribution["INCOME"] == 30


def test_risk_momentum_deteriorating():
    report = module.build_portfolio_risk_intelligence(
        allocations=base_allocations(),
        prior_risk_history=[1, 1, 1],
    )
    assert report["risk_momentum"]["direction"] == "DETERIORATING"


def test_risk_momentum_improving():
    report = module.build_portfolio_risk_intelligence(
        allocations=[],
        prior_risk_history=[80, 75, 70],
    )
    assert report["risk_momentum"]["direction"] == "IMPROVING"


def test_every_metric_has_more_reference_details():
    report = build()
    for key in report["risk_categories"]:
        assert key in report["details"]
        detail = report["details"][key]
        assert detail["definition"]
        assert detail["calculation"]
        assert detail["why_it_matters"]
    assert "risk_momentum" in report["details"]
    assert "overall_portfolio_risk" in report["details"]


def test_markdown_contains_full_names_and_more_links():
    markdown = module.format_portfolio_risk_markdown(build())
    assert "Overall Portfolio Risk" in markdown
    assert "Underlying Exposure Risk" in markdown
    assert "Decision Risk" in markdown
    assert "More..." in markdown
    assert "Paper-Only Safety" in markdown


def test_html_is_created_and_contains_report(tmp_path):
    report = module.write_portfolio_risk_intelligence(
        {"allocations": base_allocations()},
        root_path=str(tmp_path),
    )
    assert report["module_name"] == module.MODULE_NAME
    assert (tmp_path / "portfolio_risk_intelligence.json").exists()
    assert (tmp_path / "portfolio_risk_intelligence.md").exists()
    html_path = tmp_path / "portfolio_risk_intelligence.html"
    assert html_path.exists()
    assert "Portfolio Risk Intelligence" in html_path.read_text(encoding="utf-8")


def test_empty_portfolio_is_valid_with_warning():
    report = module.build_portfolio_risk_intelligence(allocations=[])
    assert report["allocation_count"] == 0
    assert report["warnings"]
    assert report["errors"] == []
    assert math_is_finite(report["overall_portfolio_risk_score"])
    assert report["overall_portfolio_risk_label"] in module.RISK_LABELS[0][1:] + tuple(label for _, label in module.RISK_LABELS)


def test_malformed_allocations_rejected():
    with pytest.raises(ValueError):
        module.build_portfolio_risk_intelligence(allocations="not-a-sequence")


def test_nonfinite_numbers_are_sanitized():
    report = module.build_portfolio_risk_intelligence(
        allocations=[
            {
                "allocation_id": "TEST",
                "allocation_percent": float("inf"),
                "projected_income": float("nan"),
                "leverage_multiplier": float("inf"),
            }
        ]
    )
    assert report["total_allocation_percent"] == 0
    assert math_is_finite(report["overall_portfolio_risk_score"])


def math_is_finite(value):
    import math
    return math.isfinite(float(value))


def test_no_broker_or_order_execution_imports():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["import robin_stocks", "import alpaca", "submit_order(", "place_order(", "broker.login"]
    assert not any(item in source for item in forbidden)
