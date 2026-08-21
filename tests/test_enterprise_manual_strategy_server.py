from io import BytesIO
from urllib.parse import urlencode

import dividend_bot.enterprise_manual_strategy_server as server


def _environ(method="POST", path=server.MANUAL_STRATEGY_PATH, body=b""):
    return {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
        "wsgi.input": BytesIO(body),
    }


def _body() -> bytes:
    return urlencode(
        [
            ("strategy_id", "NFLX_TEST"),
            ("name", "NFLX Test"),
            ("underlying_symbol", "NFLX"),
            ("direction", "LONG"),
            ("timeframe", "1D"),
            ("number_of_entries", "2"),
            ("rule_logic", "ALL"),
            ("entry_rule_left", "close"),
            ("entry_rule_operator", ">"),
            ("entry_rule_right", "ema"),
            ("entry_rule_period", "20"),
        ]
    ).encode()


def test_manual_strategy_post_is_intercepted_and_saved_by_swing(monkeypatch) -> None:
    monkeypatch.setattr(
        server.base,
        "create_wsgi_app",
        lambda **kwargs: lambda environ, start_response: [b"base"],
    )
    captured = {}

    def fake_submit(body):
        captured["body"] = body
        return {
            "ok": True,
            "paper_trade_mode": True,
            "result": {
                "status": "SAVED",
                "strategy_id": "NFLX_TEST",
                "underlying_symbol": "NFLX",
            },
        }

    monkeypatch.setattr(server, "submit_manual_strategy_form", fake_submit)
    app = server.create_wsgi_app()
    response_status = []
    response_headers = []

    payload = b"".join(
        app(
            _environ(body=_body()),
            lambda status, headers: (response_status.append(status), response_headers.extend(headers)),
        )
    ).decode()

    assert response_status == ["200 OK"]
    assert captured["body"] == _body()
    assert "Manual Strategy Saved" in payload
    assert "NFLX_TEST" in payload
    assert "SWING-001" in payload
    assert ("Cache-Control", "no-store") in response_headers


def test_existing_portal_routes_delegate_unchanged(monkeypatch) -> None:
    calls = []

    def base_app(environ, start_response):
        calls.append((environ["REQUEST_METHOD"], environ["PATH_INFO"]))
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"delegated"]

    monkeypatch.setattr(server.base, "create_wsgi_app", lambda **kwargs: base_app)
    app = server.create_wsgi_app()
    statuses = []
    payload = b"".join(
        app(
            _environ(method="GET", path="/cash"),
            lambda status, headers: statuses.append(status),
        )
    )

    assert payload == b"delegated"
    assert calls == [("GET", "/cash")]
    assert statuses == ["200 OK"]


def test_invalid_swing_submission_returns_400_without_falling_into_base(monkeypatch) -> None:
    monkeypatch.setattr(
        server.base,
        "create_wsgi_app",
        lambda **kwargs: lambda environ, start_response: [b"should-not-run"],
    )
    monkeypatch.setattr(
        server,
        "submit_manual_strategy_form",
        lambda body: (_ for _ in ()).throw(ValueError("invalid rules")),
    )
    app = server.create_wsgi_app()
    statuses = []
    payload = b"".join(
        app(
            _environ(body=_body()),
            lambda status, headers: statuses.append(status),
        )
    ).decode()

    assert statuses == ["400 Bad Request"]
    assert "Manual Strategy Not Saved" in payload
    assert "invalid rules" in payload


def test_manual_strategy_route_rejects_non_form_content_type(monkeypatch) -> None:
    monkeypatch.setattr(
        server.base,
        "create_wsgi_app",
        lambda **kwargs: lambda environ, start_response: [b"base"],
    )
    app = server.create_wsgi_app()
    environ = _environ(body=_body())
    environ["CONTENT_TYPE"] = "application/json"
    statuses = []

    payload = b"".join(
        app(environ, lambda status, headers: statuses.append(status))
    ).decode()

    assert statuses == ["400 Bad Request"]
    assert "application/x-www-form-urlencoded" in payload


def test_manual_strategy_route_is_paper_only() -> None:
    assert server.PAPER_TRADE_MODE is True
    assert server.LIVE_TRADING_ENABLED is False
    assert server.BROKER_EXECUTION_ENABLED is False
    assert server.ORDER_PLACEMENT_ENABLED is False
    assert server.CAPITAL_MOVEMENT_ENABLED is False
