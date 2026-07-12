import json
from pathlib import Path

import pytest

import wealth_attribution_engine as module


def sample_kwargs():
    return {
        "period_start": "2026-07-01",
        "period_end": "2026-07-12",
        "starting_portfolio_value": 500.0,
        "ending_portfolio_value": 539.2,
        "capital_appreciation": [{"allocation": "AMDW + PLTU", "amount": 21.55, "percentage": 4.31}],
        "dividend_income": [{"allocation": "AMDW", "amount": 10.40, "percentage": 2.08}],
        "sgov_interest": [{"allocation": "SGOV", "amount": 1.30, "percentage": 0.26}],
        "estimated_protection_value": [{"allocation": "PLTU protection", "amount": 3.70, "percentage": 0.74}],
        "replacement_value_created": [{"allocation": "QQQI to AMDW", "amount": 3.05, "percentage": 0.61}],
        "portfolio_turnover_impact": [{"allocation": "Friction", "amount": -0.80, "percentage": -0.16}],
    }


def test_public_functions_exist():
    for name in [
        "build_wealth_attribution",
        "format_wealth_attribution_markdown",
        "format_wealth_attribution_html",
        "write_wealth_attribution",
        "build_and_write_wealth_attribution",
    ]:
        assert callable(getattr(module, name))


def test_paper_only_flags():
    report = module.build_wealth_attribution(**sample_kwargs())
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_builds_all_frozen_metrics():
    report = module.build_wealth_attribution(**sample_kwargs())
    labels = [item["label"] for item in report["metrics"]]
    assert labels == [
        "Capital Appreciation",
        "Dividend Income",
        "SGOV Interest",
        "Estimated Protection Value",
        "Replacement Value Created",
        "Portfolio Turnover Impact",
    ]


def test_every_metric_has_details_reference_and_explanation():
    report = module.build_wealth_attribution(**sample_kwargs())
    for metric in report["metrics"] + [report["net_total_wealth_contribution"]]:
        assert metric["details_link"].startswith("#details-")
        assert metric["details"]["what_it_is"]
        assert metric["details"]["how_calculated"]
        assert metric["details"]["why_it_matters"]
        assert "contributors" in metric["details"]


def test_total_wealth_change_and_reconciliation():
    report = module.build_wealth_attribution(**sample_kwargs())
    assert report["observed_total_wealth_change"] == pytest.approx(39.2)
    assert report["observed_total_wealth_change_percentage"] == pytest.approx(7.84)
    assert report["explained_change"] == pytest.approx(39.2)
    assert report["unexplained_change"] == pytest.approx(0.0)


def test_primary_driver_and_largest_drag():
    report = module.build_wealth_attribution(**sample_kwargs())
    assert report["primary_driver"] == "Capital Appreciation"
    assert report["largest_drag"] == "Portfolio Turnover Impact"


def test_estimated_metrics_are_explicitly_labeled():
    report = module.build_wealth_attribution(**sample_kwargs())
    estimates = {item["metric_id"]: item["details"]["is_estimate"] for item in report["metrics"]}
    assert estimates["estimated_protection_value"] is True
    assert estimates["replacement_value_created"] is True
    assert estimates["portfolio_turnover_impact"] is True
    assert estimates["capital_appreciation"] is False
    assert any("estimates" in warning.lower() for warning in report["warnings"])


def test_unexplained_change_creates_warning():
    kwargs = sample_kwargs()
    kwargs["ending_portfolio_value"] = 550.0
    report = module.build_wealth_attribution(**kwargs)
    assert report["unexplained_change"] == pytest.approx(10.8)
    assert any("do not fully reconcile" in warning for warning in report["warnings"])


def test_empty_contributors_are_valid():
    report = module.build_wealth_attribution(
        period_start="2026-07-01",
        period_end="2026-07-02",
        starting_portfolio_value=500,
        ending_portfolio_value=500,
    )
    assert report["observed_total_wealth_change"] == 0
    assert all(item["amount"] == 0 for item in report["metrics"])


def test_malformed_records_rejected():
    kwargs = sample_kwargs()
    kwargs["capital_appreciation"] = ["bad"]
    with pytest.raises(ValueError):
        module.build_wealth_attribution(**kwargs)


def test_missing_period_rejected():
    kwargs = sample_kwargs()
    kwargs["period_start"] = ""
    with pytest.raises(ValueError):
        module.build_wealth_attribution(**kwargs)


def test_negative_portfolio_value_rejected():
    kwargs = sample_kwargs()
    kwargs["starting_portfolio_value"] = -1
    with pytest.raises(ValueError):
        module.build_wealth_attribution(**kwargs)


def test_nonfinite_values_default_safely():
    kwargs = sample_kwargs()
    kwargs["capital_appreciation"] = [{"allocation": "AMDW", "amount": float("inf"), "percentage": float("nan")}]
    report = module.build_wealth_attribution(**kwargs)
    metric = report["metrics"][0]
    assert metric["amount"] == 0
    assert metric["percentage"] == 0


def test_markdown_contains_details_links_and_interpretation():
    report = module.build_wealth_attribution(**sample_kwargs())
    markdown = module.format_wealth_attribution_markdown(report)
    assert "[Details](#details-capital-appreciation)" in markdown
    assert "What is it?" in markdown
    assert "How is it calculated?" in markdown
    assert "Why does it matter?" in markdown
    assert "How to Interpret This Report" in markdown


def test_html_contains_expandable_details():
    report = module.build_wealth_attribution(**sample_kwargs())
    output = module.format_wealth_attribution_html(report)
    assert "<details" in output
    assert "<summary>Details</summary>" in output
    assert "details-capital-appreciation" in output
    assert "What is it?" in output


def test_write_outputs(tmp_path: Path):
    report = module.build_wealth_attribution(**sample_kwargs())
    paths = module.write_wealth_attribution(report, root_path=str(tmp_path))
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    assert Path(paths["html"]).exists()
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["module_name"] == module.MODULE_NAME


def test_build_and_write_outputs(tmp_path: Path):
    report = module.build_and_write_wealth_attribution(root_path=str(tmp_path), **sample_kwargs())
    assert set(report["output_files"]) == {"json", "markdown", "html"}


def test_source_contains_no_broker_or_order_execution_calls():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["place_order(", "submit_order(", "execute_trade(", "robin_stocks", "requests.post(", "subprocess.", "os.system("]
    assert not any(term in source for term in forbidden)
