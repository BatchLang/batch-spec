#!/usr/bin/env python3
"""Validate batch-spec YAML files and corpus fixtures against JSON Schema."""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

import jsonschema
import yaml

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import (  # noqa: E402
    COMMANDS_YAML,
    CORPUS_DIR,
    DOCS_DIR,
    EXPANSION_YAML,
    REPO_ROOT,
    SCHEMA_DIR,
)

LOGGER = logging.getLogger(__name__)

# Allow tab/LF/CR only among C0 controls in consumer docs and corpus inputs.
_ALLOWED_C0 = {9, 10, 13}

# Corpus fixtures that intentionally begin with a UTF-8 BOM for encoding probes.
_BOM_ALLOWED_INPUTS = frozenset(
    {
        "utf8-bom-first-token-invalid",
    }
)

_README_VERSION_RE = re.compile(
    r"currently\s+\*\*(?P<version>\d+\.\d+\.\d+)\*\*",
    re.IGNORECASE,
)


def _validate_yaml(path: Path, schema_path: Path) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SystemExit(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        raise SystemExit(f"Empty YAML document: {path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=data, schema=schema)
    print(f"OK {path.name}")


def _validate_json(path: Path, schema: dict[str, object]) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        raise SystemExit(
            f"Schema validation failed for {path.as_posix()}: {exc.message}"
        ) from exc
    rel = path.relative_to(REPO_ROOT)
    print(f"OK {rel.as_posix()}")


def _check_utf8_c0(path: Path, *, allow_bom: bool) -> list[str]:
    """Return human-readable encoding/C0 failures for a text file."""
    failures: list[str] = []
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [f"{path.relative_to(REPO_ROOT).as_posix()}: cannot read ({exc})"]
    if allow_bom and data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    elif data.startswith(b"\xef\xbb\xbf"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        failures.append(f"{rel}: unexpected UTF-8 BOM")
        data = data[3:]
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        failures.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {exc}")
        return failures
    bad = [
        f"0x{byte:02x}@{index}"
        for index, byte in enumerate(data)
        if byte < 32 and byte not in _ALLOWED_C0
    ]
    if bad:
        rel = path.relative_to(REPO_ROOT).as_posix()
        sample = ", ".join(bad[:5])
        failures.append(f"{rel}: disallowed C0 controls ({sample})")
    return failures


def _validate_docs_encoding() -> None:
    """Reject C0 control characters (except tab/LF/CR) in docs/*.md."""
    failures: list[str] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        failures.extend(_check_utf8_c0(path, allow_bom=False))
    if failures:
        for message in failures:
            print(message, file=sys.stderr)
            LOGGER.error("%s", message)
        raise SystemExit(1)
    for path in sorted(DOCS_DIR.glob("*.md")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        print(f"OK {rel}")


def _validate_corpus_input_encoding(input_path: Path) -> list[str]:
    case_id = input_path.parent.name
    allow_bom = case_id in _BOM_ALLOWED_INPUTS
    return _check_utf8_c0(input_path, allow_bom=allow_bom)


def _validate_corpus() -> None:
    schema_path = SCHEMA_DIR / "parse-expect.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    orphan_expects: list[Path] = []
    orphan_inputs: list[Path] = []
    encoding_failures: list[str] = []
    for expect_path in sorted(CORPUS_DIR.glob("**/expect.json")):
        input_path = expect_path.parent / "input.cmd"
        if not input_path.is_file():
            orphan_expects.append(expect_path)
            continue
        _validate_json(expect_path, schema)
        encoding_failures.extend(_validate_corpus_input_encoding(input_path))
    for input_path in sorted(CORPUS_DIR.glob("**/input.cmd")):
        expect_path = input_path.parent / "expect.json"
        if not expect_path.is_file():
            orphan_inputs.append(input_path)
    if encoding_failures:
        for message in encoding_failures:
            print(message, file=sys.stderr)
            LOGGER.error("%s", message)
        raise SystemExit(1)
    if orphan_expects or orphan_inputs:
        for path in orphan_expects:
            rel = path.relative_to(REPO_ROOT)
            print(f"Missing input.cmd for {rel.as_posix()}", file=sys.stderr)
            LOGGER.error("Missing input.cmd for %s", rel.as_posix())
        for path in orphan_inputs:
            rel = path.relative_to(REPO_ROOT)
            print(f"Missing expect.json for {rel.as_posix()}", file=sys.stderr)
            LOGGER.error("Missing expect.json for %s", rel.as_posix())
        raise SystemExit(1)


def _read_version_file() -> str:
    version_path = REPO_ROOT / "VERSION"
    try:
        text = version_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SystemExit(f"Cannot read VERSION: {exc}") from exc
    if not re.fullmatch(r"\d+\.\d+\.\d+", text):
        raise SystemExit(f"VERSION must be MAJOR.MINOR.PATCH, got {text!r}")
    return text


def _validate_version_sync() -> None:
    """Ensure VERSION, pyproject.toml, and README agree."""
    version = _read_version_file()
    pyproject_path = REPO_ROOT / "pyproject.toml"
    try:
        pyproject_text = pyproject_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Cannot read pyproject.toml: {exc}") from exc
    match = re.search(
        r'(?m)^version\s*=\s*"(?P<version>\d+\.\d+\.\d+)"\s*$',
        pyproject_text,
    )
    if match is None:
        raise SystemExit('pyproject.toml missing project version = "X.Y.Z"')
    py_version = match.group("version")
    if py_version != version:
        raise SystemExit(
            f"VERSION ({version}) != pyproject.toml version ({py_version})"
        )

    readme_path = REPO_ROOT / "README.md"
    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Cannot read README.md: {exc}") from exc
    readme_match = _README_VERSION_RE.search(readme_text)
    if readme_match is None:
        raise SystemExit("README.md missing 'currently **X.Y.Z**' version marker")
    readme_version = readme_match.group("version")
    if readme_version != version:
        raise SystemExit(
            f"VERSION ({version}) != README.md currently **{readme_version}**"
        )
    print(f"OK VERSION sync ({version})")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )
    _validate_version_sync()
    _validate_yaml(COMMANDS_YAML, SCHEMA_DIR / "commands.schema.json")
    _validate_yaml(EXPANSION_YAML, SCHEMA_DIR / "expansion.schema.json")
    _validate_docs_encoding()
    _validate_corpus()
    print("batch-spec validation passed")


if __name__ == "__main__":
    main()
