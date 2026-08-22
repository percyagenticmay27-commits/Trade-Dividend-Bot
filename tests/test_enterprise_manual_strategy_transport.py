import json
from pathlib import Path

import pytest

import dividend_bot.enterprise_manual_strategy_transport as transport


class Completed:
    def __init__(self, *, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _runtime(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "swing"
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("stub", encoding="utf-8")
    return root, python


def test_transport_invokes_swing_cli_without_shell_or_direct_storage_write(tmp_path: Path, monkeypatch) -> None:
    root, python = _runtime(tmp_path)
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return Completed(
            stdout=json.dumps({
                "ok": True,
                "paper_trade_mode": True,
                "result": {"status": "SAVED", "strategy_id": "NFLX_TEST"},
            })
        )

    monkeypatch.setattr(transport.subprocess, "run", fake_run)
    response = transport.submit_manual_strategy_to_swing(
        {"strategy_id": "NFLX_TEST"},
        swing_root=root,
        swing_python=python,
    )

    assert response["ok"] is True
    assert captured["args"] == [str(python.resolve()), "-m", transport.SWING_INTAKE_MODULE]
    assert captured["cwd"] == root.resolve()
    assert "shell" not in captured
    assert json.loads(captured["input"])["strategy_id"] == "NFLX_TEST"


def test_transport_rejects_swing_validation_failure(tmp_path: Path, monkeypatch) -> None:
    root, python = _runtime(tmp_path)
    monkeypatch.setattr(
        transport.subprocess,
        "run",
        lambda *a, **k: Completed(
            returncode=2,
            stdout=json.dumps({"ok": False, "paper_trade_mode": True, "error": "invalid"}),
        ),
    )
    with pytest.raises(ValueError, match="invalid"):
        transport.submit_manual_strategy_to_swing({}, swing_root=root, swing_python=python)


def test_transport_rejects_non_paper_response(tmp_path: Path, monkeypatch) -> None:
    root, python = _runtime(tmp_path)
    monkeypatch.setattr(
        transport.subprocess,
        "run",
        lambda *a, **k: Completed(returncode=0, stdout=json.dumps({"ok": True, "paper_trade_mode": False})),
    )
    with pytest.raises(RuntimeError, match="paper-only"):
        transport.submit_manual_strategy_to_swing({}, swing_root=root, swing_python=python)


def test_transport_surfaces_process_failure_when_cli_returns_no_json(tmp_path: Path, monkeypatch) -> None:
    root, python = _runtime(tmp_path)
    monkeypatch.setattr(
        transport.subprocess,
        "run",
        lambda *a, **k: Completed(returncode=1, stderr="TypeError: bad strategy payload"),
    )
    with pytest.raises(ValueError, match="bad strategy payload"):
        transport.submit_manual_strategy_to_swing({}, swing_root=root, swing_python=python)


def test_transport_fails_closed_when_swing_runtime_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="repository root"):
        transport.submit_manual_strategy_to_swing({}, swing_root=tmp_path / "missing")


def test_transport_preserves_swing_venv_python_symlink_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The Swing venv interpreter must not resolve to the system Python."""

    root = tmp_path / "swing"
    venv_python = root / ".venv/bin/python"
    system_python = tmp_path / "usr/bin/python3.12"

    venv_python.parent.mkdir(parents=True)
    system_python.parent.mkdir(parents=True)
    system_python.write_text("stub", encoding="utf-8")
    venv_python.symlink_to(system_python)

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return Completed(
            stdout=json.dumps(
                {
                    "ok": True,
                    "paper_trade_mode": True,
                    "result": {
                        "status": "SAVED",
                        "strategy_id": "SYMLINK_TEST",
                    },
                }
            )
        )

    monkeypatch.setattr(transport.subprocess, "run", fake_run)

    response = transport.submit_manual_strategy_to_swing(
        {"strategy_id": "SYMLINK_TEST"},
        swing_root=root,
    )

    expected_venv_python = root.resolve() / ".venv/bin/python"

    assert response["ok"] is True
    assert captured["args"][0] == str(expected_venv_python)

    # Critical regression: never collapse the venv interpreter
    # to its underlying system-Python target.
    assert captured["args"][0] != str(system_python.resolve())

    assert captured["args"][1:] == [
        "-m",
        transport.SWING_INTAKE_MODULE,
    ]
    assert captured["cwd"] == root.resolve()
    assert "shell" not in captured
