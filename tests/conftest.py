"""Shared pytest fixtures for batch-spec."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
CONFORMANCE_DIR = REPO_ROOT / "conformance"
GENERATED_DIR = REPO_ROOT / "generated" / "python"

_REQUIRED_PARSER_FILES = (
    "BatchLexer.py",
    "BatchParser.py",
    "BatchParserVisitor.py",
    "__init__.py",
    ".grammar-stamp",
)


def _parser_files_present() -> bool:
    return all((GENERATED_DIR / name).is_file() for name in _REQUIRED_PARSER_FILES)


def _ensure_generated_parser() -> None:
    if _parser_files_present():
        LOGGER.debug("Using committed generated parser at %s", GENERATED_DIR)
        return

    antlr4 = shutil.which("antlr4")
    if antlr4 is None:
        pytest.skip("Generated parser missing and antlr4 CLI is unavailable")

    LOGGER.info("Generated parser missing; running scripts/generate_parser.py")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "generate_parser.py")],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        pytest.fail(f"Failed to generate parser: {message}")

    if not _parser_files_present():
        pytest.fail("Parser generation completed but required files are still missing")


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def generated_parser() -> None:
    _ensure_generated_parser()


@pytest.fixture
def tmp_corpus(tmp_path: Path) -> Path:
    corpus_root = tmp_path / "corpus" / "parse"
    corpus_root.mkdir(parents=True)
    return corpus_root
