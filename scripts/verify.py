#!/usr/bin/env python3
"""Local verification pipeline for batch-spec."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import REPO_ROOT  # noqa: E402

LOGGER = logging.getLogger(__name__)

_PYTHON_TARGETS = ("scripts", "conformance", "tests")
_LINT_TARGETS = _PYTHON_TARGETS
_TYPE_TARGETS = _PYTHON_TARGETS


def _build_steps(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    steps: list[tuple[str, list[str]]] = []

    if not args.skip_format:
        steps.append(("format", ["black", "--check", *_PYTHON_TARGETS]))
        steps.append(("imports", ["isort", "--check-only", *_PYTHON_TARGETS]))

    if not args.skip_lint:
        steps.append(("lint", ["pylint", *_LINT_TARGETS]))

    steps.append(
        (
            "yamllint",
            [sys.executable, "-m", "yamllint", "--strict", "."],
        )
    )

    if not args.skip_types:
        steps.append(("types", ["mypy", *_TYPE_TARGETS]))

    steps.extend(
        [
            ("validate", [sys.executable, "scripts/validate.py"]),
            ("generate", [sys.executable, "scripts/generate_parser.py", "--check"]),
            (
                "test",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "--cov=scripts",
                    "--cov=conformance",
                    "--cov-fail-under=90",
                ],
            ),
        ]
    )

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


def _run_step(name: str, command: Sequence[str]) -> int:
    LOGGER.info("Starting step: %s", name)
    LOGGER.debug("Command: %s", " ".join(command))
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    if result.returncode == 0:
        LOGGER.info("Step passed: %s", name)
    else:
        LOGGER.error("Step failed: %s (exit code %s)", name, result.returncode)
    return result.returncode


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the batch-spec verification pipeline"
    )
    parser.add_argument("--skip-format", action="store_true")
    parser.add_argument("--skip-lint", action="store_true")
    parser.add_argument("--skip-types", action="store_true")
    parser.add_argument("--skip-conformance", action="store_true")
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
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
