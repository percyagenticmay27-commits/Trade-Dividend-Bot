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


def _swing_row():
    return {
        "strategy_id": "SWING-001",
        "watchlist_count": 4,
        "watchlist": [
            {
                "underlying_symbol": "NVDA",
                "leveraged_symbol": "NVDX",
                "lifecycle_status": "WATCHLIST",
                "watchlist_rank": 1,
                "theme": "AI Infrastructure",
                "promotion_eligible": True,
                "promotion_readiness": {
                    "trusted_sources": {"status": "FAIL", "value": 4, "threshold": 5, "reason": "Need <five> sources", "sources": ["SEC", "Reuters"]},
                    "financial_health": {"status": "PENDING", "value": None, "threshold": 70, "reason": "Financial <health> unavailable"},
                    "theme_strength": {"status": "PENDING", "value": None, "threshold": 70, "reason": "Theme <strength> unavailable"},
                    "opportunity_quality": {"status": "PASS", "value": 82.854, "threshold": 70, "reason": "OQ <strong> good", "evidence_source": "oq.json", "provenance": "Swing runtime"},
                    "thesis_integrity": {"status": "PASS", "value": True, "reason": "Thesis <ok>", "evidence_available": True, "source": "thesis.json"},
                    "entry": {"status": "PASS", "value": 70.0, "threshold": 70, "reason": "Entry <ready>", "source_path": "entry.json"},
                    "promotion_ready": False,
                    "blocking_reasons": ["trusted_sources: <blocked>"],
                },
            },
            {
                "underlying_symbol": "IREN",
                "leveraged_symbol": "IREL",
                "lifecycle_status": "DISCOVERY",
                "watchlist_rank": 2,
                "theme": None,
            },
            {
                "underlying_symbol": "BE",
                "leveraged_symbol": None,
                "lifecycle_status": "MONITOR",
                "watchlist_rank": 3,
                "theme": "Clean Energy",
                "promotion_readiness": {"promotion_ready": True},
            },
            {
                "underlying_symbol": "AMZN",
                "leveraged_symbol": "AMZU",
                "lifecycle_status": "WATCHLIST",
                "watchlist_rank": 4,
                "promotion_eligible": True,
            },
        ],
    }


def _swing_table(page: str) -> str:
    start = page.index("<table class='watchlist-table candidate-pipeline-table'>")
    end = page.index("</table>", start) + len("</table>")
    return page[start:end]


def test_swing_main_table_has_exact_compact_headings():
    table = _swing_table(render_watchlist_panel(_swing_row()))
    assert "<thead><tr><th>Rank</th><th>Symbol</th><th>Vehicle</th><th>Status</th><th>Theme</th><th>OQ</th><th>Thesis</th><th>Entry</th><th>Promotion</th></tr></thead>" in table


def test_old_oversized_headings_absent_from_swing_main_table():
    table = _swing_table(render_watchlist_panel(_swing_row()))
    for heading in ("Capacity Status", "Trusted Sources", "Theme Strength", "Blocking Gates", "Composite Score", "Win Rate", "Paper Return"):
        assert f"<th>{heading}</th>" not in table


def test_watchlist_rank_renders_only_for_watchlist_records():
    table = _swing_table(render_watchlist_panel(_swing_row()))
    assert "<td class='num'>1</td>" in table
    assert table.count("<td class='num'>—</td>") == 2
    assert "Not reported" not in table.split("<tbody>", 1)[1].split("</tbody>", 1)[0].split("<td class='num'>", 1)[1].split("</td>", 1)[0]


def test_missing_theme_renders_em_dash():
    table = _swing_table(render_watchlist_panel(_swing_row()))
    assert "<strong>IREN</strong>" in table
    iren = table.split("<strong>IREN</strong>", 1)[1].split("</tr>", 1)[0]
    assert "<td>—</td>" in iren


def test_oq_uses_authoritative_nested_score_status_and_expandable_detail():
    page = render_watchlist_panel(_swing_row())
    assert "82.9 PASS" in page
    oq_main = page.split("<strong>NVDA</strong>", 1)[1].split("</tr>", 1)[0]
    assert "aria-controls='watchlist-promotion-detail-1'" in oq_main
    assert "Open opportunity quality details" in oq_main
    detail = page.split("id='watchlist-promotion-detail-1'", 1)[1].split("</tr>", 1)[0]
    assert "Opportunity Quality" in detail
    assert "82.854" in detail
    assert "70" in detail
    assert "OQ &lt;strong&gt; good" in detail
    assert "oq.json" in detail
    assert "Swing runtime" in detail


def test_thesis_uses_authoritative_status_and_expandable_detail():
    page = render_watchlist_panel(_swing_row())
    nvda_main = page.split("<strong>NVDA</strong>", 1)[1].split("</tr>", 1)[0]
    assert "Open thesis integrity details" in nvda_main
    assert ">PASS</span>" in nvda_main
    detail = page.split("id='watchlist-promotion-detail-1'", 1)[1].split("</tr>", 1)[0]
    assert "Thesis Integrity" in detail
    assert ">true<" in detail
    assert "thesis.json" in detail


def test_entry_uses_authoritative_score_status_and_expandable_detail():
    page = render_watchlist_panel(_swing_row())
    nvda_main = page.split("<strong>NVDA</strong>", 1)[1].split("</tr>", 1)[0]
    assert "70 PASS" in nvda_main
    assert "Open entry details" in nvda_main
    detail = page.split("id='watchlist-promotion-detail-1'", 1)[1].split("</tr>", 1)[0]
    assert "Entry Readiness" in detail
    assert "70.0" in detail
    assert "entry.json" in detail


def test_promotion_no_has_six_gate_detail_and_blocking_reasons():
    page = render_watchlist_panel(_swing_row())
    assert ">NO</span>" in page
    assert "class='watchlist-promotion-toggle'" in page
    assert "aria-expanded='false'" in page
    assert "aria-controls='watchlist-promotion-detail-1'" in page
    assert "id='watchlist-promotion-detail-1' class='watchlist-promotion-detail-row' hidden" in page
    assert "<td colspan='9'>" in page
    for gate in ("Trusted Sources", "Financial Health", "Theme Strength", "Opportunity Quality", "Thesis Integrity", "Entry Readiness"):
        assert f"<strong>{gate}</strong>" in page
    assert page.count("class='watchlist-promotion-gate-card'") >= 6
    assert "trusted_sources: &lt;blocked&gt;" in page
    assert "SEC, Reuters" in page


def test_promotion_yes_only_from_authoritative_true():
    page = render_watchlist_panel(_swing_row())
    assert page.count(">YES</span>") == 1
    assert page.count(">NO</span>") == 1


def test_missing_promotion_readiness_is_pending_not_legacy_inference():
    page = render_watchlist_panel(_swing_row())
    amzn_main = page.split("<strong>AMZN</strong>", 1)[1].split("</tr>", 1)[0]
    assert "PENDING" in amzn_main
    assert ">YES</span>" not in amzn_main
    assert "aria-controls='watchlist-promotion-detail-4'" in amzn_main
    amzn_detail = page.split("id='watchlist-promotion-detail-4'", 1)[1].split("</tr>", 1)[0]
    assert "Authoritative Promotion Readiness evidence is unavailable." in amzn_detail


def test_pending_financial_health_and_theme_strength_remain_pending_not_zero():
    page = render_watchlist_panel(_swing_row())
    promo = page.split("Six-gate Promotion Readiness", 1)[1].split("Blocking reasons", 1)[0]
    assert "<strong>Financial Health</strong> <span class='watchlist-status watchlist-status-neutral'>PENDING</span>" in promo
    assert "<strong>Theme Strength</strong> <span class='watchlist-status watchlist-status-neutral'>PENDING</span>" in promo
    assert "Value:</span> <strong>0" not in promo


def test_html_escaping_for_reasons_and_evidence():
    page = render_watchlist_panel(_swing_row())
    for raw in ("<five>", "<health>", "<strength>", "<ok>", "<ready>", "<blocked>"):
        assert raw not in page
    assert "&lt;five&gt;" in page
    assert "&lt;blocked&gt;" in page


def test_non_swing_behavior_remains_compatible():
    page = render_watchlist_panel({"strategy_id": "DIVIDEND-001", "watchlist_count": 1, "watchlist": [{"symbol": "AAA", "rank": 1, "status": "WATCH", "entry_score": 82.5, "entry_confidence": 77, "entry_confidence_level": "HIGH", "market_data_stale": False, "currently_held": False}]})
    assert "<th>Candidate</th>" in page
    assert "Entry Score" in page
    assert "Confidence" in page
    assert "82.5" in page
    assert "77.0 (High)" in page


def test_css_supports_native_details_drilldowns():
    css = watchlist_ui_css()
    assert ".watchlist-qa-details" in css
    assert ".watchlist-qa-body" in css
    assert ".candidate-pipeline-table{min-width:0" in css
    assert ".watchlist-promotion-detail-row[hidden]{display:none}" in css
    assert ".watchlist-promotion-gates{display:grid;grid-template-columns:repeat(6" in css
    assert ".watchlist-promotion-gate-header" in css


def test_promotion_toggle_script_controls_only_its_detail_row():
    page = render_watchlist_panel(_swing_row())
    assert "watchlist-promotion-toggle" in page
    assert "watchlist-detail-toggle" in page
    assert "toggle.getAttribute('aria-controls')" in page
    assert "detailRow.hidden = !nextExpanded" in page
    assert "aria-expanded" in page
