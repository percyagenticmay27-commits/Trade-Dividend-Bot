from __future__ import annotations

import io
import urllib.error
from email.message import Message

import pytest

from src.dividend_bot.provider_symbol_normalizer import normalize_symbol
from src.dividend_bot.stooq_market_data_source import (
    ProviderAwareStooqSource,
    StooqDataUnavailable,
)


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("SOXL", "soxl.us"),
        ("TQQQ", "tqqq.us"),
        ("SPY", "spy.us"),
        ("AAPL", "aapl.us"),
        ("BRK.B", "brk.b"),
    ],
)
def test_stooq_symbol_normalization(symbol: str, expected: str) -> None:
    assert normalize_symbol(symbol, "STOOQ").provider_symbol == expected


def test_quote_and_history_use_same_normalized_download_url(monkeypatch) -> None:
    urls: list[str] = []
    csv_body = (
        b"Date,Open,High,Low,Close,Volume\n"
        b"2026-08-04,100,110,99,108,12345\n"
    )

    class Response:
        status = 200
        headers = Message()
        headers["Content-Type"] = "text/csv"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return csv_body

    def fake_urlopen(request, timeout=15):
        urls.append(request.full_url)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    source = ProviderAwareStooqSource()

    quote = source.get_quote("SOXL")
    history = source.get_history("SOXL", "1mo", "1d")

    assert quote["price"] == 108.0
    assert history["bars"][-1]["close"] == "108"
    assert len(urls) == 2
    assert urls[0] == urls[1]
    assert "s=soxl.us" in urls[0]
    assert "i=d" in urls[0]


def test_stooq_404_is_classified_as_download_endpoint_failure(monkeypatch) -> None:
    def fake_urlopen(request, timeout=15):
        raise urllib.error.HTTPError(
            request.full_url,
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(
        StooqDataUnavailable,
        match=r"STOOQ_DOWNLOAD_ENDPOINT_HTTP_404 symbol=tqqq\.us",
    ):
        ProviderAwareStooqSource().get_history("TQQQ", "1mo", "1d")


def test_stooq_html_response_is_rejected(monkeypatch) -> None:
    class Response:
        status = 200
        headers = Message()
        headers["Content-Type"] = "text/html"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"<html><body>download unavailable</body></html>"

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=15: Response())

    with pytest.raises(StooqDataUnavailable, match="STOOQ_NON_CSV_RESPONSE"):
        ProviderAwareStooqSource().get_history("AAPL", "1mo", "1d")
