"""Tests for scripts/verify.py."""

# Private helpers are the subject of these tests; the rcfile cannot scope that check.
# The antlr-lint command is repeated so a change to the verify step fails the test.
# pylint: disable=protected-access,duplicate-code

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import verify  # noqa: E402  # pylint: disable=wrong-import-position


def test_build_steps_includes_all_defaults() -> None:
    args = verify._parse_args([])
    steps = verify._build_steps(args)
    names = [name for name, _ in steps]
    assert names == [
        "uv-lock",
        "autopep8",
        "isort",
        "pyproject-fmt",
        "black",
        "yamllint",
        "pymarkdown",
        "antlr-lint",
        "mypy",
        "pylint",
        "bandit",
        "validate",
        "generate",
        "pytest",
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


def test_antlr_lint_checks_the_grammar_directory() -> None:
    args = verify._parse_args([])
    steps = dict(verify._build_steps(args))
    assert steps["antlr-lint"] == [
        "antlr-lint",
        "lint",
        "--no-colors",
        "--severity",
        "error",
        "--disable-rule",
        "S003",
        "--disable-rule",
        "N002",
        "grammar",
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
    assert names == [
        "uv-lock",
        "yamllint",
        "pymarkdown",
        "antlr-lint",
        "bandit",
        "validate",
        "generate",
        "pytest",
    ]


def test_build_steps_skip_pytest_omits_the_suite() -> None:
    args = verify._parse_args(["--skip-pytest"])
    names = [name for name, _ in verify._build_steps(args)]
    assert "pytest" not in names
    assert "conformance" in names


def test_fix_rewrites_formatters_and_leaves_black_as_a_check() -> None:
    args = verify._parse_args(["--fix"])
    steps = dict(verify._build_steps(args))
    assert "--in-place" in steps["autopep8"]
    assert "--diff" not in steps["autopep8"]
    assert "--check-only" not in steps["isort"]
    assert "--stdout" not in steps["pyproject-fmt"]
    assert "--check" in steps["black"]


def test_default_formatters_are_checks() -> None:
    args = verify._parse_args([])
    steps = dict(verify._build_steps(args))
    assert "--diff" in steps["autopep8"]
    assert "--exit-code" in steps["autopep8"]
    assert "--check-only" in steps["isort"]
    assert "--stdout" in steps["pyproject-fmt"]
    assert steps["uv-lock"] == ["uv", "lock", "--check"]
    assert steps["bandit"][1:3] == ["-m", "bandit"]
    assert "scripts" in steps["bandit"]
    assert "conformance" in steps["bandit"]
    assert "tests" not in steps["bandit"]


def test_pylint_uses_one_job_on_python_315(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 15, 0, "final", 0))
    command = verify._pylint_command()
    assert command[-2:] == ["-j", "1"]


def test_pylint_uses_default_jobs_before_python_315(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 14, 0, "final", 0))
    command = verify._pylint_command()
    assert "-j" not in command


def test_parse_args_verbose_enables_debug_logging() -> None:
    args = verify._parse_args(["--verbose"])
    assert args.verbose is True


def test_run_step_returns_subprocess_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    assert verify._run_step("example", ["echo", "ok"]) == 0
    mock_run.assert_called_once()


def test_run_step_hides_antlr_lint_parser_diagnostics(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stderr="token error"))
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    with caplog.at_level(logging.DEBUG):
        assert verify._run_step("antlr-lint", ["antlr-lint", "lint", "grammar"]) == 0

    assert mock_run.call_args.kwargs["stderr"] is subprocess.PIPE
    assert mock_run.call_args.kwargs["text"] is True
    assert mock_run.call_args.kwargs["env"]["PYTHONUTF8"] == "1"
    assert mock_run.call_args.kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
    debug_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.DEBUG
    ]
    info_or_higher = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.INFO
    ]
    assert any("token error" in message for message in debug_messages)
    assert all("token error" not in message for message in info_or_higher)


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


def test_run_step_reports_missing_uv(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("verify.shutil.which", lambda _name: None)

    with caplog.at_level(logging.ERROR):
        assert verify._run_step("uv-lock", ["uv", "lock", "--check"]) == 1

    assert "uv is required" in caplog.text


def test_run_pylint_writes_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
    mock_run = MagicMock(
        return_value=MagicMock(returncode=0, stdout="rated 10/10\n", stderr="")
    )
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    assert verify._run_step("pylint", ["pylint"]) == 0
    report = tmp_path / "pylint-output.txt"
    assert report.read_text(encoding="utf-8") == "rated 10/10\n"
    assert "rated 10/10" in capsys.readouterr().out


def test_pyproject_fmt_check_passes_when_formatted_text_matches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    text = '[project]\nname = "batch-spec"\nversion = "0.0.0"\n'
    (tmp_path / "pyproject.toml").write_text(text, encoding="utf-8")
    monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout=text, stderr=""))
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    command = [sys.executable, "-m", "pyproject_fmt", "--stdout", "pyproject.toml"]
    assert verify._run_step("pyproject-fmt", command) == 0


def test_pyproject_fmt_check_reports_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    original = '[project]\nname = "batch-spec"\nversion = "0.0.0"\n'
    formatted = '[project]\nname = "batch-spec"\nversion = "0.0.1"\n'
    (tmp_path / "pyproject.toml").write_text(original, encoding="utf-8")
    monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
    mock_run = MagicMock(
        return_value=MagicMock(returncode=0, stdout=formatted, stderr="")
    )
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    command = [sys.executable, "-m", "pyproject_fmt", "--stdout", "pyproject.toml"]
    assert verify._run_step("pyproject-fmt", command) == 1
    assert 'version = "0.0.1"' in capsys.readouterr().out


def test_pyproject_fmt_check_keeps_the_project_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = '[project]\nname = "batch-spec"\n'
    renamed = '[project]\nname = "batch_spec"\n'
    (tmp_path / "pyproject.toml").write_text(original, encoding="utf-8")
    monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
    mock_run = MagicMock(
        return_value=MagicMock(returncode=0, stdout=renamed, stderr="")
    )
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    command = [sys.executable, "-m", "pyproject_fmt", "--stdout", "pyproject.toml"]
    assert verify._run_step("pyproject-fmt", command) == 0


def test_pyproject_fmt_check_fails_when_stdout_is_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    text = '[project]\nname = "batch-spec"\n'
    (tmp_path / "pyproject.toml").write_text(text, encoding="utf-8")
    monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
    mock_run = MagicMock(return_value=MagicMock(returncode=2, stdout="", stderr="boom"))
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    command = [sys.executable, "-m", "pyproject_fmt", "--stdout", "pyproject.toml"]
    assert verify._run_step("pyproject-fmt", command) == 2


def test_pyproject_fmt_fix_restores_the_project_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "batch-spec"\n', encoding="utf-8")
    monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)

    def _rewrite(_command: list[str], **_kwargs: object) -> MagicMock:
        pyproject.write_text('[project]\nname = "batch_spec"\n', encoding="utf-8")
        return MagicMock(returncode=0)

    monkeypatch.setattr("verify.subprocess.run", _rewrite)
    command = [sys.executable, "-m", "pyproject_fmt", "pyproject.toml"]
    assert verify._run_step("pyproject-fmt", command) == 0
    assert 'name = "batch-spec"' in pyproject.read_text(encoding="utf-8")


def test_pyproject_fmt_fix_returns_formatter_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "batch-spec"\n', encoding="utf-8"
    )
    monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
    mock_run = MagicMock(return_value=MagicMock(returncode=3))
    monkeypatch.setattr("verify.subprocess.run", mock_run)

    command = [sys.executable, "-m", "pyproject_fmt", "pyproject.toml"]
    assert verify._run_step("pyproject-fmt", command) == 3


def test_pyproject_fmt_rejects_a_missing_project_table(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "pyproject.toml").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)

    assert verify._run_step("pyproject-fmt", ["pyproject-fmt", "--stdout"]) == 1


def test_set_project_name_requires_an_assignment() -> None:
    with pytest.raises(ValueError, match="missing"):
        verify._set_project_name('[project]\nversion = "0"\n', "batch-spec")
