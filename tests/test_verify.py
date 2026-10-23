"""Tests for scripts/verify.py."""

# Private helpers are the subject of these tests; the rcfile cannot scope that check.
# pylint: disable=protected-access

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import verify  # noqa: E402


def test_build_steps_includes_all_defaults() -> None:
    args = verify._parse_args([])
    steps = verify._build_steps(args)
    names = [name for name, _ in steps]
    assert names == [
        "format",
        "imports",
        "lint",
        "yamllint",
        "types",
        "validate",
        "generate",
        "test",
        "pip-audit",
        "conformance",
    ]


def test_yamllint_checks_the_repository_root() -> None:
    args = verify._parse_args([])
    steps = dict(verify._build_steps(args))
    assert steps["yamllint"] == [
        sys.executable,
        "-m",
        "yamllint",
        "--strict",
        ".",
    ]


def test_build_steps_honors_skip_flags() -> None:
    args = verify._parse_args(
        [
            "--skip-format",
            "--skip-lint",
            "--skip-types",
            "--skip-conformance",
            "--skip-audit",
        ]
    )
    steps = verify._build_steps(args)
    names = [name for name, _ in steps]
    assert names == ["yamllint", "validate", "generate", "test"]


def test_parse_args_verbose_enables_debug_logging() -> None:
    args = verify._parse_args(["--verbose"])
    assert args.verbose is True


def test_run_step_returns_subprocess_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    assert verify._run_step("example", ["echo", "ok"]) == 0
    mock_run.assert_called_once()


def test_run_step_logs_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    mock_run = MagicMock(return_value=MagicMock(returncode=2))
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    with caplog.at_level(logging.ERROR):
        assert verify._run_step("lint", ["pylint"]) == 2

    assert "Step failed: lint" in caplog.text


def test_main_returns_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        verify,
        "_build_steps",
        lambda _args: [("lint", ["pylint"]), ("test", ["pytest"])],
    )
    monkeypatch.setattr(
        verify, "_run_step", lambda name, _cmd: 1 if name == "lint" else 0
    )

    assert verify.main([]) == 1


def test_main_returns_zero_when_all_steps_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        verify,
        "_build_steps",
        lambda _args: [("validate", ["python", "scripts/validate.py"])],
    )
    monkeypatch.setattr(verify, "_run_step", lambda _name, _cmd: 0)

    assert verify.main([]) == 0


def test_main_configures_verbose_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify, "_build_steps", lambda _args: [])
    monkeypatch.setattr(verify, "_run_step", lambda _name, _cmd: 0)

    assert verify.main(["--verbose"]) == 0
