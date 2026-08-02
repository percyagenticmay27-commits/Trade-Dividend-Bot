from __future__ import annotations

from src.dividend_bot.strategy_decision_journal_renderer import (
    render_strategy_decision_journal,
    render_strategy_decision_journal_document,
)


def _journal(images: list[dict]) -> dict:
    return {
        "strategy_id": "DIVIDEND-001",
        "strategy_name": "Dividend Income Strategy",
        "strategy_kind": "DIVIDEND",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only": True,
        "decisions": [
            {
                "decision_id": "DIV-001",
                "strategy_id": "DIVIDEND-001",
                "decision_timestamp": "2026-08-02T12:00:00Z",
                "decision_type": "SELECT_PAIR",
                "status": "RECORDED",
                "final_rationale": "Evidence supports the selected pair.",
                "alternatives": [],
                "committee_evidence": [],
                "images": images,
                "ecosystem": {
                    "ecosystem_name": "NVIDIA Income Ecosystem",
                    "income_leg": "NVDY",
                    "leverage_leg": "NVDX",
                },
            }
        ],
    }


def test_gallery_renders_strategy_owned_thumbnail() -> None:
    value = render_strategy_decision_journal(
        _journal(
            [
                {
                    "path": "images/nvdy-nvdx.png",
                    "caption": "NVDY and NVDX comparison",
                    "image_type": "PAIR_COMPARISON",
                }
            ]
        )
    )

    assert "journal-gallery-thumb" in value
    assert 'src="images/nvdy-nvdx.png"' in value
    assert "NVDY and NVDX comparison" in value
    assert "PAIR_COMPARISON" in value
    assert 'data-gallery-decision="DIV-001"' in value


def test_gallery_preserves_multiple_image_order() -> None:
    value = render_strategy_decision_journal(
        _journal(
            [
                {"path": "images/first.png", "caption": "First", "image_type": "CHART"},
                {"path": "images/second.png", "caption": "Second", "image_type": "REPORT"},
            ]
        )
    )

    assert value.index("images/first.png") < value.index("images/second.png")
    assert 'data-gallery-index="0"' in value
    assert 'data-gallery-index="1"' in value


def test_gallery_links_to_full_size_image_without_script() -> None:
    value = render_strategy_decision_journal(
        _journal(
            [{"path": "images/chart.png", "caption": "Chart", "image_type": "CHART"}]
        )
    )

    assert 'href="images/chart.png"' in value
    assert 'target="_blank"' in value
    assert 'rel="noopener noreferrer"' in value
    assert "<script>" not in value


def test_gallery_escapes_untrusted_caption() -> None:
    value = render_strategy_decision_journal(
        _journal(
            [
                {
                    "path": "images/chart.png",
                    "caption": "<script>alert(1)</script>",
                    "image_type": "CHART",
                }
            ]
        )
    )

    assert "<script>alert(1)</script>" not in value
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in value


def test_gallery_rejects_unsafe_image_uri() -> None:
    value = render_strategy_decision_journal(
        _journal(
            [
                {
                    "path": "javascript:alert(1)",
                    "caption": "Unsafe",
                    "image_type": "CHART",
                }
            ]
        )
    )

    assert "javascript:alert(1)" not in value
    assert "Image unavailable" in value


def test_empty_image_gallery_remains_explanatory() -> None:
    value = render_strategy_decision_journal(_journal([]))

    assert "No images reported for this decision." in value


def test_standalone_document_contains_gallery_styles() -> None:
    value = render_strategy_decision_journal_document(
        _journal(
            [{"path": "images/chart.png", "caption": "Chart", "image_type": "CHART"}]
        )
    )

    assert "journal-gallery-thumb" in value
    assert 'target="_blank"' in value
    assert "<script>" not in value
