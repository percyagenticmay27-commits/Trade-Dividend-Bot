from src.dividend_bot.enterprise_watchlist_ui import render_watchlist_panel, watchlist_ui_css


def _row():
    return {
        "strategy_id": "DIVIDEND-001",
        "watchlist_count": 2,
        "watchlist": [
            {
                "symbol": "AAA",
                "name": "Alpha Income ETF",
                "rank": 1,
                "status": "WATCH",
                "entry_score": 82.5,
                "entry_status": "WAIT",
                "entry_confidence": 77,
                "entry_confidence_level": "HIGH",
                "timing_context": "WAITING_FOR_ENTRY",
                "entry_reasons": ["MOMENTUM_NOT_CONFIRMED"],
                "requirements_for_buy": ["PRICE_ABOVE_EMA20", "STRATEGY_A_BUY"],
                "market_data_stale": False,
                "currently_held": False,
                "sources": ["candidate_discovery.json"],
            },
            {
                "symbol": "BBB",
                "rank": 2,
                "status": "READY_FOR_SCORING",
                "market_data_stale": True,
                "currently_held": True,
                "sources": ["TEST"],
            },
        ],
    }


def test_watchlist_renderer_uses_professional_summary_and_table():
    page = render_watchlist_panel(_row())
    assert "2 candidates" in page
    assert "Total Watchlist" in page
    assert "Ready / Promoted" in page
    assert "Currently Held" in page
    assert "Stale Market Data" in page
    assert "Alpha Income ETF" in page
    assert "Entry Score" in page
    assert "Confidence" in page
    assert "Why It Has Not Progressed" in page
    assert "What Happens Next" in page
    assert "Evidence As-Of" in page
    assert "Waiting for Price above ema20; Strategy a buy." in page
    assert "Re-evaluate after the listed requirements are satisfied." in page
    assert "Market Data" in page


def test_watchlist_renderer_does_not_fabricate_missing_scores():
    page = render_watchlist_panel(_row())
    assert "watchlist-not-reported'>Not reported" in page
    assert "82.5" in page
    assert "77.0 (High)" in page


def test_watchlist_renderer_preserves_market_freshness_and_status():
    page = render_watchlist_panel(_row())
    assert ">WAIT<" in page
    assert "READY_FOR_SCORING" in page
    assert "Current symbol-level entry evidence is unavailable." in page
    assert "FRESH" in page
    assert "STALE" in page


def test_watchlist_renderer_has_explicit_zero_candidate_state():
    page = render_watchlist_panel({"strategy_id": "DIVIDEND-001", "watchlist_count": 0, "watchlist": []})
    assert "0 candidates" in page
    assert "No active strategy watchlist candidates." in page
    assert "explicitly marks them for watchlist monitoring" in page


def test_watchlist_renderer_escapes_strategy_owned_text():
    row = _row()
    row["watchlist"][0]["name"] = "<script>alert(1)</script>"
    row["watchlist"][0]["sources"] = ["<b>bad</b>"]
    page = render_watchlist_panel(row)
    assert "<script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<b>bad</b>" not in page


def test_watchlist_css_is_self_contained_and_responsive():
    css = watchlist_ui_css()
    assert css.lstrip().startswith("<style>")
    assert css.rstrip().endswith("</style>")
    assert ".watchlist-table" in css
    assert ".watchlist-summary-grid" in css
    assert ".watchlist-status-ready" in css
    assert "@media(max-width:520px)" in css


def test_swing_candidate_pipeline_renders_all_published_lifecycle_rows():
    page = render_watchlist_panel({
        "strategy_id": "SWING-001",
        "watchlist_count": 3,
        "watchlist": [
            {
                "underlying_symbol": "NBIS",
                "leveraged_symbol": "NEBX",
                "lifecycle_status": "WATCHLIST",
                "capacity_status": "ACTIVE",
                "watchlist_rank": 1,
                "composite_score": 91.2,
                "financial_health": "STRONG",
                "theme": "AI Infrastructure",
                "promotion_eligible": True,
                "source_count": 5,
                "win_rate": 62.5,
                "paper_return": 8.4,
            },
            {
                "underlying_symbol": "IREN",
                "leveraged_symbol": "IREL",
                "lifecycle_status": "DISCOVERY",
                "capacity_status": "ACTIVE",
                "watchlist_rank": 2,
            },
            {
                "underlying_symbol": "BE",
                "leveraged_symbol": None,
                "lifecycle_status": "REMOVED",
                "capacity_status": "REMOVED",
                "watchlist_rank": 3,
            },
        ],
    })

    assert "Candidate Pipeline" in page
    assert "Total Candidate Records</span><strong>3" in page
    assert "Active Watchlist</span><strong>1" in page
    assert "Discovery</span><strong>1" in page
    assert "Removed</span><strong>1" in page
    assert "NBIS" in page and "NEBX" in page
    assert "IREN" in page and "IREL" in page
    assert ">BE<" in page
    assert ">WATCHLIST<" in page
    assert ">DISCOVERY<" in page
    assert ">REMOVED<" in page
    for heading in (
        "Underlying Symbol",
        "Leveraged Symbol",
        "Lifecycle Status",
        "Capacity Status",
        "Watchlist Rank",
        "Trusted Sources",
        "Financial Health",
        "Theme",
        "Theme Strength",
        "Opportunity Quality",
        "Thesis Integrity",
        "Entry Readiness",
        "Promotion Ready",
        "Blocking Gates",
        "Composite Score",
        "Win Rate",
        "Paper Return",
    ):
        assert heading in page

    assert "Promotion Eligible" not in page


def test_watchlist_count_never_fabricates_candidate_rows():
    page = render_watchlist_panel({
        "strategy_id": "SWING-001",
        "watchlist_count": 3,
        "watchlist": [],
    })

    assert "3 candidates" in page
    assert "reports 3 candidate records" in page
    assert "Candidate rows are never fabricated" in page
    assert "<tbody>" not in page

def test_swing_candidate_pipeline_supports_exact_published_field_names():
    page = render_watchlist_panel({
        "strategy_id": "SWING-001",
        "watchlist_count": 2,
        "watchlist": [
            {
                "underlying_symbol": "NBIS",
                "leveraged_symbol": "NEBX",
                "watchlist_status": "WATCHLIST",
                "capacity_status": "ACTIVE",
                "watchlist_rank": 1,
                "financial_health_score": 77.29,
                "themes": "AI Infrastructure;Data Centers",
                "promotion_eligible": False,
            },
            {
                "underlying_symbol": "BE",
                "leveraged_symbol": "",
                "watchlist_status": "REMOVED",
                "capacity_status": "REMOVED",
                "watchlist_rank": None,
                "themes": "Clean Energy",
                "promotion_eligible": False,
            },
        ],
    })

    assert "AI Infrastructure;Data Centers" in page
    assert "Clean Energy" in page

    # Legacy financial_health_score and promotion_eligible remain source fields,
    # but they are not authoritative Promotion Readiness evidence.
    assert "77.29" not in page
    assert ">NO<" not in page
    assert "Promotion Eligible" not in page

    # Missing authoritative Promotion Readiness renders unavailable/PENDING.
    assert "PENDING" in page
    assert "watchlist-not-reported'>Not reported" in page
    assert ">WATCHLIST<" in page
    assert ">REMOVED<" in page



def test_swing_candidate_pipeline_renders_authoritative_promotion_readiness():
    page = render_watchlist_panel({
        "strategy_id": "SWING-001",
        "watchlist_count": 1,
        "watchlist": [
            {
                "underlying_symbol": "NVDA",
                "leveraged_symbol": "NVDX",
                "lifecycle_status": "WATCHLIST",
                "capacity_status": "ACTIVE",
                "watchlist_rank": 1,
                "theme": "AI Infrastructure",
                "promotion_eligible": True,
                "promotion_readiness": {
                    "trusted_sources": {
                        "status": "FAIL",
                        "value": 4.0,
                        "threshold": 5.0,
                        "reason": "Source Confluence 4 is below threshold 5",
                    },
                    "financial_health": {
                        "status": "PENDING",
                        "value": None,
                        "threshold": 70.0,
                        "reason": "Financial Health evidence is unavailable",
                    },
                    "theme_strength": {
                        "status": "PENDING",
                        "value": None,
                        "threshold": 70.0,
                        "reason": "Theme Momentum evidence is unavailable",
                    },
                    "opportunity_quality": {
                        "status": "PASS",
                        "value": 82.854,
                        "threshold": 70.0,
                        "reason": "Opportunity Quality 82.854 meets threshold 70",
                    },
                    "thesis_integrity": {
                        "status": "PASS",
                        "value": True,
                        "threshold": True,
                        "reason": "Thesis integrity passed",
                    },
                    "entry": {
                        "status": "PASS",
                        "value": 70.0,
                        "threshold": 70.0,
                        "reason": "Entry Score 70 meets threshold 70",
                    },
                    "promotion_ready": False,
                    "blocking_reasons": [
                        "trusted_sources: Source Confluence 4 is below threshold 5"
                    ],
                },
            }
        ],
    })

    for heading in (
        "Trusted Sources",
        "Financial Health",
        "Theme Strength",
        "Opportunity Quality",
        "Thesis Integrity",
        "Entry Readiness",
        "Promotion Ready",
        "Blocking Gates",
    ):
        assert heading in page

    assert "AI Infrastructure" in page
    assert "82.854" in page
    assert "70" in page
    assert "Source Confluence 4 is below threshold 5" in page

    # Legacy promotion_eligible=True must not override authoritative readiness.
    assert "Promotion Eligible" not in page
    assert "Promotion Ready" in page
    assert ">NO<" in page


def test_swing_candidate_pipeline_does_not_infer_missing_promotion_readiness():
    page = render_watchlist_panel({
        "strategy_id": "SWING-001",
        "watchlist_count": 1,
        "watchlist": [
            {
                "underlying_symbol": "AMZN",
                "leveraged_symbol": "AMZU",
                "lifecycle_status": "WATCHLIST",
                "capacity_status": "ACTIVE",
                "watchlist_rank": 1,
                "promotion_eligible": True,
            }
        ],
    })

    assert "Promotion Ready" in page
    assert "Promotion Eligible" not in page

    # The legacy True value must not produce a readiness YES.
    assert ">YES<" not in page
    assert "PENDING" in page
    assert "Not reported" in page
