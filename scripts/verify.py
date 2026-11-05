#!/usr/bin/env python3
"""Local verification pipeline for batch-spec."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import difflib
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import REPO_ROOT  # noqa: E402  # pylint: disable=wrong-import-position

LOGGER = logging.getLogger(__name__)

_PYTHON_TARGETS = ("scripts", "conformance", "tests")
_PYPROJECT = "pyproject.toml"
_PYLINT_REPORT = "pylint-output.txt"
_SECURITY_DIRS = ("scripts", "conformance")


def _autopep8_command(*, fix: bool) -> list[str]:
    """Return the trailing-whitespace autopep8 command.

    ``--diff`` alone exits 0 when it would rewrite a file. ``--exit-code``
    makes that difference fail the gate. ``--fix`` rewrites instead.
    """
    command = [sys.executable, "-m", "autopep8", "--select=W291,W293"]
    if fix:
        command.append("--in-place")
    else:
        command.extend(["--diff", "--exit-code"])
    command.extend(["-r", *_PYTHON_TARGETS])
    return command


def _isort_command(*, fix: bool) -> list[str]:
    """Return the isort command. ``--fix`` rewrites imports."""
    command = [sys.executable, "-m", "isort"]
    if not fix:
        command.append("--check-only")
    command.extend(_PYTHON_TARGETS)
    return command


def _pyproject_fmt_command(*, fix: bool) -> list[str]:
    """Return the pyproject-fmt command.

    Check mode prints the formatted file on stdout. Fix mode rewrites it.
    """
    command = [sys.executable, "-m", "pyproject_fmt"]
    if not fix:
        command.append("--stdout")
    command.append(_PYPROJECT)
    return command


def _pylint_command() -> list[str]:
    """Return the pylint command.

    Parallel jobs pickle the linter. On Python 3.15, dill cannot pickle code
    objects (``co_lnotab`` was removed), so the pool crashes before any file
    is checked. One process avoids that.
    """
    command = [sys.executable, "-m", "pylint", *_PYTHON_TARGETS]
    if sys.version_info >= (3, 15):
        command.extend(["-j", "1"])
    return command


def _format_steps(*, fix: bool) -> list[tuple[str, list[str]]]:
    """Return formatter steps. Black stays check-only."""
    return [
        ("autopep8", _autopep8_command(fix=fix)),
        ("isort", _isort_command(fix=fix)),
        ("pyproject-fmt", _pyproject_fmt_command(fix=fix)),
        ("black", [sys.executable, "-m", "black", "--check", *_PYTHON_TARGETS]),
    ]


def _build_steps(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    """Return verification steps in run order, honoring skip flags."""
    steps: list[tuple[str, list[str]]] = [("uv-lock", ["uv", "lock", "--check"])]
    if not args.skip_format:
        steps.extend(_format_steps(fix=args.fix))
    steps.extend(
        [
            ("yamllint", [sys.executable, "-m", "yamllint", "--strict", "."]),
            (
                "pymarkdown",
                [
                    sys.executable,
                    "-m",
                    "pymarkdown",
                    "--strict-config",
                    "scan",
                    "--recurse",
                    "--respect-gitignore",
                    ".",
                ],
            ),
            (
                "antlr-lint",
                [
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
                ],
            ),
        ]
    )
    if not args.skip_types:
        steps.append(("mypy", [sys.executable, "-m", "mypy", *_PYTHON_TARGETS]))
    if not args.skip_lint:
        steps.append(("pylint", _pylint_command()))
    steps.append(
        (
            "bandit",
            [
                sys.executable,
                "-m",
                "bandit",
                "-r",
                *_SECURITY_DIRS,
                "-c",
                _PYPROJECT,
                "-ll",
                "-q",
            ],
        )
    )
    steps.extend(
        [
            ("validate", [sys.executable, "scripts/validate.py"]),
            ("generate", [sys.executable, "scripts/generate_parser.py", "--check"]),
        ]
    )
    if not args.skip_pytest:
        steps.append(("pytest", [sys.executable, "-m", "pytest"]))
    if not args.skip_audit:
        steps.append(
            (
                "pip-audit",
                [
                    sys.executable,
                    "-m",
                    "pip_audit",
                    "-r",
                    "requirements.txt",
                    "-r",
                    "requirements-dev.txt",
                ],
            )
        )
    if not args.skip_conformance:
        steps.append(
            (
                "conformance",
                [sys.executable, "conformance/run_parser.py", "--impl", "antlr"],
            )
        )
    return steps


def _parse_project_name(pyproject_text: str) -> str:
    """Return [project].name from pyproject.toml text."""
    data_object: object = tomllib.loads(pyproject_text)
    if not isinstance(data_object, dict):
        raise ValueError("pyproject.toml must contain a top-level table")
    project_object: object = data_object.get("project")
    if not isinstance(project_object, dict):
        raise ValueError("pyproject.toml must contain a [project] table")
    name_object: object = project_object.get("name")
    if not isinstance(name_object, str) or not name_object:
        raise ValueError("pyproject.toml [project].name must be a non-empty string")
    return name_object


def _set_project_name(pyproject_text: str, name: str) -> str:
    """Replace the [project] name assignment without touching other tables."""
    lines = pyproject_text.splitlines()
    in_project = False
    replaced = False
    updated: list[str] = []
    for line in lines:
        if line.strip() == "[project]":
            in_project = True
            updated.append(line)
            continue
        if in_project and line.startswith("[") and line.strip() != "[project]":
            in_project = False
        if in_project and not replaced:
            stripped = line.lstrip()
            if stripped.startswith("name ="):
                prefix = line[: len(line) - len(stripped)]
                updated.append(f'{prefix}name = "{name}"')
                replaced = True
                continue
        updated.append(line)
    if not replaced:
        raise ValueError("pyproject.toml missing [project].name assignment")
    trailing_newline = "\n" if pyproject_text.endswith("\n") else ""
    return "\n".join(updated) + trailing_newline


def _read_project(pyproject_path: Path) -> tuple[str, str]:
    """Return pyproject text and its [project].name."""
    original = pyproject_path.read_text(encoding="utf-8")
    return original, _parse_project_name(original)


def _apply_pyproject_fmt(
    command: Sequence[str], pyproject_path: Path, project_name: str
) -> int:
    """Rewrite pyproject.toml, then put the project name back."""
    result = subprocess.run(list(command), cwd=REPO_ROOT, check=False)
    if result.returncode != 0:
        return result.returncode
    if not pyproject_path.is_file():
        LOGGER.error("pyproject-fmt removed %s", pyproject_path)
        return 1
    formatted = pyproject_path.read_text(encoding="utf-8")
    pyproject_path.write_text(
        _set_project_name(formatted, project_name),
        encoding="utf-8",
        newline="\n",
    )
    return 0


def _print_pyproject_diff(original: str, expected: str) -> None:
    """Print a unified diff for a pyproject.toml formatting mismatch."""
    diff = difflib.unified_diff(
        original.splitlines(),
        expected.splitlines(),
        fromfile=_PYPROJECT,
        tofile=_PYPROJECT,
    )
    for line in diff:
        print(line)


def _check_pyproject_fmt(
    command: Sequence[str], original: str, project_name: str
) -> int:
    """Fail when pyproject-fmt would change pyproject.toml."""
    result = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not result.stdout.strip():
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        LOGGER.error("pyproject-fmt produced no formatted output")
        return result.returncode or 1
    expected = _set_project_name(result.stdout, project_name)
    if expected.rstrip("\n") != original.rstrip("\n"):
        _print_pyproject_diff(original, expected)
        return 1
    return 0


def _run_pyproject_fmt(command: Sequence[str]) -> int:
    """Run pyproject-fmt while preserving the [project].name value."""
    pyproject_path = REPO_ROOT / _PYPROJECT
    try:
        original, project_name = _read_project(pyproject_path)
    except (OSError, ValueError) as exc:
        LOGGER.error("Cannot read %s: %s", pyproject_path, exc)
        return 1
    if "--stdout" in command:
        return _check_pyproject_fmt(command, original, project_name)
    return _apply_pyproject_fmt(command, pyproject_path, project_name)


def _run_pylint(command: Sequence[str]) -> int:
    """Run pylint and write a UTF-8 report beside the repository root."""
    result = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report_path = REPO_ROOT / _PYLINT_REPORT
    report_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(
            result.stderr,
            end="" if result.stderr.endswith("\n") else "\n",
            file=sys.stderr,
        )
    return result.returncode


def _run_command(name: str, command: Sequence[str]) -> int:
    """Run one command. antlr-lint's grammar-parser noise stays at debug."""
    capture_parser_diagnostics = name == "antlr-lint"
    env = None
    if capture_parser_diagnostics:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        check=False,
        stderr=subprocess.PIPE if capture_parser_diagnostics else None,
        text=capture_parser_diagnostics,
        encoding="utf-8" if capture_parser_diagnostics else None,
        errors="replace" if capture_parser_diagnostics else None,
        env=env,
    )
    if capture_parser_diagnostics and result.stderr:
        LOGGER.debug("antlr-lint parser diagnostics:\n%s", result.stderr)
    return result.returncode


def _run_step(name: str, command: Sequence[str]) -> int:
    """Run one verification step and return its exit code."""
    LOGGER.info("Starting step: %s", name)
    LOGGER.debug("Command: %s", " ".join(command))
    if name == "uv-lock" and shutil.which(command[0]) is None:
        LOGGER.error("uv is required for `uv lock --check` but was not found on PATH")
        return 1
    if name == "pylint":
        exit_code = _run_pylint(command)
    elif name == "pyproject-fmt":
        exit_code = _run_pyproject_fmt(command)
    else:
        exit_code = _run_command(name, command)
    if exit_code == 0:
        LOGGER.info("Step passed: %s", name)
    else:
        LOGGER.error("Step failed: %s (exit code %s)", name, exit_code)
    return exit_code


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse verify.py flags."""
    parser = argparse.ArgumentParser(
        description="Run the batch-spec verification pipeline"
    )
    parser.add_argument("--skip-format", action="store_true")
    parser.add_argument("--skip-lint", action="store_true")
    parser.add_argument("--skip-types", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--skip-conformance", action="store_true")
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply autopep8, isort, and pyproject-fmt fixes before checks",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the verification pipeline. Return the first failing exit code."""
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    for name, command in _build_steps(args):
        exit_code = _run_step(name, command)
        if exit_code != 0:
            return exit_code

    LOGGER.info("All verification steps passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
