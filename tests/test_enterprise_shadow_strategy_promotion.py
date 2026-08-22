from io import BytesIO
from urllib.parse import urlencode

import dividend_bot.enterprise_manual_strategy_server as server


def _environ(body: bytes):
    return {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": server.SHADOW_PROMOTION_PATH,
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
        "wsgi.input": BytesIO(body),
    }


def test_shadow_promotion_route_requires_explicit_user_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(server.base, "create_wsgi_app", lambda **kwargs: lambda environ, start_response: [b"base"])
    app = server.create_wsgi_app()
    body = urlencode({"underlying_symbol": "NFLX", "strategy_id": "SHADOW_B"}).encode()
    statuses = []
    payload = b"".join(app(_environ(body), lambda status, headers: statuses.append(status))).decode()
    assert statuses == ["400 Bad Request"]
    assert "explicit user confirmation" in payload


def test_shadow_promotion_route_delegates_only_after_user_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(server.base, "create_wsgi_app", lambda **kwargs: lambda environ, start_response: [b"base"])
    captured = {}

    def fake_promote(submission):
        captured.update(submission)
        return {
            "ok": True,
            "paper_trade_mode": True,
            "result": {
                "status": "PROMOTED",
                "underlying_symbol": "NFLX",
                "promoted_strategy_id": "SHADOW_B",
                "previous_direct_strategy_id": "DIRECT_A",
            },
        }

    monkeypatch.setattr(server, "promote_shadow_strategy_in_swing", fake_promote)
    app = server.create_wsgi_app()
    body = urlencode({"underlying_symbol": "NFLX", "strategy_id": "SHADOW_B", "user_confirmed": "yes"}).encode()
    statuses = []
    payload = b"".join(app(_environ(body), lambda status, headers: statuses.append(status))).decode()
    assert statuses == ["200 OK"]
    assert captured == {"underlying_symbol": "NFLX", "strategy_id": "SHADOW_B", "user_confirmed": True}
    assert "Shadow Strategy Promoted" in payload
    assert "Previous Direct strategy: DIRECT_A" in payload


def test_shadow_promotion_server_has_no_auto_promotion_or_execution_authority() -> None:
    assert server.AUTO_PROMOTION_ENABLED is False
    assert server.PAPER_TRADE_MODE is True
    assert server.LIVE_TRADING_ENABLED is False
    assert server.BROKER_EXECUTION_ENABLED is False
    assert server.ORDER_PLACEMENT_ENABLED is False
    assert server.CAPITAL_MOVEMENT_ENABLED is False
