from enterprise_discovery_financial_health import (
    REQUIRED_COMPONENTS,
    attach_candidate_financial_health,
    build_financial_health_block,
)
from enterprise_weekly_market_discovery import build_swing_projection, build_weekly_discovery
from scripts.collect_enterprise_discovery_sources import _refresh_financial_health_for_active_candidates
from scripts.generate_enterprise_weekly_market_discovery import _merge_fresh_shared_evidence


def _history(start: float, step: float, *, stale: bool = False):
    rows = []
    for index in range(22):
        rows.append({"date": f"2026-08-{index + 1:02d}", "close": start + step * index})
    return {
        "provider": "YAHOO_FINANCE",
        "retrieved_at_utc": "2026-09-04T15:00:00Z",
        "rows": rows,
        "is_stale": stale,
    }


def _fundamentals(**overrides):
    payload = {
        "provider": "YAHOO_FINANCE",
        "retrieved_at_utc": "2026-09-04T15:00:00Z",
        "symbol": "NVDA",
        "sector": "Technology",
        "revenue_growth": 0.25,
        "eps_growth": 0.30,
        "operating_cash_flow": 700.0,
        "total_revenue": 1000.0,
        "gross_margin_current": 0.75,
        "gross_margin_prior": 0.72,
        "debt_to_equity": 40.0,
        "analyst_revisions_available": True,
        "analyst_upgrades_90d": 4,
        "analyst_downgrades_90d": 1,
        "is_stale": False,
    }
    payload.update(overrides)
    return payload


def test_complete_financial_health_block_contains_all_seven_components():
    block = build_financial_health_block(
        "NVDA",
        _fundamentals(),
        _history(100.0, 1.0),
        _history(100.0, 0.25),
        sector_benchmark="XLK",
    )
    assert block is not None
    assert set(block["components"]) == set(REQUIRED_COMPONENTS)
    assert all(0.0 <= value <= 100.0 for value in block["components"].values())
    assert block["evidence_timestamp"] == "2026-09-04T15:00:00Z"
    assert "YAHOO_FINANCE" in block["provenance"]
    assert block["evidence"]["sector_benchmark"] == "XLK"


def test_missing_required_evidence_omits_block_instead_of_zero_filling():
    block = build_financial_health_block(
        "NVDA",
        _fundamentals(gross_margin_prior=None),
        _history(100.0, 1.0),
        _history(100.0, 0.25),
        sector_benchmark="XLK",
    )
    assert block is None


def test_stale_evidence_omits_block():
    block = build_financial_health_block(
        "NVDA",
        _fundamentals(is_stale=True),
        _history(100.0, 1.0),
        _history(100.0, 0.25),
        sector_benchmark="XLK",
    )
    assert block is None


class _FakeService:
    def __init__(self):
        self.financial_calls = []

    def get_financial_health_inputs(self, symbol, force_refresh=False):
        self.financial_calls.append(symbol)
        if symbol == "AMD":
            return _fundamentals(symbol="AMD", gross_margin_prior=None)
        return _fundamentals(symbol=symbol)

    def get_history(self, symbol, period="3mo", interval="1d", force_refresh=False):
        if symbol == "SPY":
            return _history(100.0, 0.25)
        return _history(100.0, 1.0)


def test_attach_refreshes_every_eligible_candidate_and_fails_closed_per_symbol():
    report = {
        "observations": [
            {"underlying_symbol": "NVDA", "nomination_eligible": True},
            {"underlying_symbol": "AMD", "nomination_eligible": True},
            {"underlying_symbol": "RESEARCH", "nomination_eligible": False},
        ],
        "warnings": [],
    }
    service = _FakeService()
    result = attach_candidate_financial_health(report, service)
    assert service.financial_calls == ["NVDA", "AMD"]
    assert "financial_health" in result["observations"][0]
    assert "financial_health" not in result["observations"][1]
    assert "financial_health" not in result["observations"][2]
    assert "incomplete or stale" in result["observations"][1]["evidence_warnings"][0]
    assert result["financial_health_policy"] == "ALL_SEVEN_COMPONENTS_REQUIRED_FAIL_CLOSED"


def test_attach_refreshes_candidate_when_nomination_eligible_is_omitted():
    report = {
        "observations": [
            {"underlying_symbol": "NVDA"},
            {"underlying_symbol": "RESEARCH", "nomination_eligible": False},
        ],
        "warnings": [],
    }
    service = _FakeService()
    result = attach_candidate_financial_health(report, service)
    assert service.financial_calls == ["NVDA"]
    assert "financial_health" in result["observations"][0]
    assert "financial_health" not in result["observations"][1]


def test_active_retained_candidate_refreshes_without_changing_nomination_state():
    report = {
        "observations": [
            {"underlying_symbol": "NVDA", "nomination_eligible": False},
            {"underlying_symbol": "RESEARCH", "nomination_eligible": False},
        ],
        "warnings": [],
    }
    service = _FakeService()
    result = _refresh_financial_health_for_active_candidates(report, service, {"NVDA"})
    assert service.financial_calls == ["NVDA"]
    assert result["observations"][0]["nomination_eligible"] is False
    assert "financial_health" in result["observations"][0]
    assert "financial_health" not in result["observations"][1]


def test_fresh_financial_health_is_merged_into_retained_candidate_before_publish():
    block = build_financial_health_block(
        "NVDA",
        _fundamentals(),
        _history(100.0, 1.0),
        _history(100.0, 0.25),
        sector_benchmark="XLK",
    )
    observations = [
        {
            "underlying_symbol": "NVDA",
            "nomination_eligible": False,
            "financial_health": block,
        }
    ]
    previous = [
        {
            "underlying_symbol": "NVDA",
            "discovery_status": "EMERGING",
            "nomination_eligible": True,
            "financial_health": None,
        }
    ]
    _merge_fresh_shared_evidence(observations, previous)
    assert previous[0]["financial_health"] == block
    assert previous[0]["nomination_eligible"] is True


def test_weekly_projection_preserves_complete_financial_health_block():
    block = build_financial_health_block(
        "NVDA",
        _fundamentals(),
        _history(100.0, 1.0),
        _history(100.0, 0.25),
        sector_benchmark="XLK",
    )
    observation = {
        "underlying_symbol": "NVDA",
        "discovery_status": "RISING",
        "themes": ["Semiconductors"],
        "source_evidence": [
            {"source": "Reuters", "mentioned_on": "2026-09-04", "story_id": "nvda-1"},
        ],
        "financial_health": block,
    }
    report = build_weekly_discovery([observation], generated_at="2026-09-04T15:05:00Z")
    swing = build_swing_projection(report)
    assert swing["candidates"][0]["financial_health"] == block


def test_weekly_projection_omits_financial_health_when_unavailable():
    observation = {
        "underlying_symbol": "NVDA",
        "discovery_status": "RISING",
        "source_evidence": [
            {"source": "Reuters", "mentioned_on": "2026-09-04", "story_id": "nvda-1"},
        ],
    }
    report = build_weekly_discovery([observation], generated_at="2026-09-04T15:05:00Z")
    swing = build_swing_projection(report)
    assert "financial_health" not in swing["candidates"][0]
