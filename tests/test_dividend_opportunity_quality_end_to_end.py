import json

from dividend_ranking_engine import build_dividend_ranking_report
from src.dividend_bot.dividend_strategy_kpi_evidence import build_dividend_strategy_kpi_evidence


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_component_reports_feed_ranking_and_enterprise_opportunity_quality(tmp_path):
    _write(tmp_path / "dividend_quality_report.json", {
        "entries": [{"symbol": "TEST", "quality_score": 80.0}],
    })
    _write(tmp_path / "momentum_score_report.json", {
        "entries": [{"symbol": "TEST", "momentum_score": 70.0}],
    })
    _write(tmp_path / "dividend_growth_report.json", {
        "entries": [{"symbol": "TEST", "growth_score": 60.0}],
    })
    _write(tmp_path / "dividend_safety_report.json", {
        "entries": [{"symbol": "TEST", "safety_score": 90.0}],
    })
    _write(tmp_path / "valuation_report.json", {
        "entries": [{"symbol": "TEST", "valuation_score": 50.0}],
    })

    ranking = build_dividend_ranking_report(root_path=str(tmp_path))
    assert ranking["ranking_count"] == 1
    assert ranking["rankings"][0]["symbol"] == "TEST"
    assert ranking["rankings"][0]["overall_score"] == 72.5

    _write(tmp_path / "dividend_rankings.json", ranking)
    _write(tmp_path / "candidate_discovery.json", {"watchlist_count": 0})
    _write(tmp_path / "results" / "strategy_performance_analytics.json", {
        "strategy_id": "DIVIDEND-001",
        "win_rate_percent": 25.0,
    })

    kpi = build_dividend_strategy_kpi_evidence(tmp_path)
    assert kpi["opportunity_quality"] == 72.5
    assert kpi["calculation_methods"]["opportunity_quality"] == "BEST_DIVIDEND_RANKING_OVERALL_SCORE"
    assert "opportunity_quality" not in kpi["missing_metrics"]
