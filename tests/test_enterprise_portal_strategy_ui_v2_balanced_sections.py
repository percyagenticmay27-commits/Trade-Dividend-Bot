from src.dividend_bot.enterprise_portal_strategy_ui_v2 import _replace_panel


def test_replace_panel_preserves_outer_workspace_section_with_nested_sections() -> None:
    source = (
        "<div class='before'>before</div>"
        "<section class='workspace-tab-panel' id='panel-DIVIDEND-001-holdings'>"
        "<section class='legacy-inner'><div>legacy</div></section>"
        "</section>"
        "<div class='after'>after</div>"
    )
    replacement = (
        "<section class='holdings-pro'>"
        "<section class='holdings-subsection'>new</section>"
        "</section>"
    )

    rendered = _replace_panel(
        source,
        sid="DIVIDEND-001",
        tab="holdings",
        body=replacement,
    )

    assert "legacy" not in rendered
    assert "holdings-pro" in rendered
    assert "holdings-subsection" in rendered
    assert "<div class='after'>after</div>" in rendered
    assert rendered.count("<section") == rendered.count("</section>")


def test_replace_panel_does_not_change_document_when_panel_is_missing() -> None:
    source = "<section id='something-else'>unchanged</section>"
    assert _replace_panel(source, sid="DIVIDEND-001", tab="income", body="new") == source
