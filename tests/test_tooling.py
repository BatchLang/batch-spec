"""Tests for scripts/ tooling modules."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import jsonschema
import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _paths  # noqa: E402
import generate_parser  # noqa: E402
import validate  # noqa: E402


def test_paths_resolve_to_existing_targets() -> None:
    assert _paths.REPO_ROOT.is_dir()
    assert _paths.DATA_DIR.is_dir()
    assert _paths.SCHEMA_DIR.is_dir()
    assert _paths.GRAMMAR_DIR.is_dir()
    assert _paths.DOCS_DIR.is_dir()
    assert _paths.CORPUS_DIR.is_dir()
    assert _paths.GENERATED_DIR.is_dir()
    assert _paths.COMMANDS_YAML.is_file()
    assert _paths.EXPANSION_YAML.is_file()


def test_validate_accepts_real_commands_yaml() -> None:
    validate._validate_yaml(
        _paths.COMMANDS_YAML, _paths.SCHEMA_DIR / "commands.schema.json"
    )


def test_validate_accepts_real_expansion_yaml() -> None:
    validate._validate_yaml(
        _paths.EXPANSION_YAML, _paths.SCHEMA_DIR / "expansion.schema.json"
    )


def test_expansion_invalid_tilde_patterns_match_bad_forms() -> None:
    """Catalog rules must catch invalid %~ forms and spare valid ones."""
    data = yaml.safe_load(_paths.EXPANSION_YAML.read_text(encoding="utf-8"))
    invalid = data["invalid_combinations"]
    patterns = [entry["pattern"] for entry in invalid if "pattern" in entry]
    assert patterns, "expected at least one invalid_combinations pattern"
    compiled = [re.compile(pattern) for pattern in patterns]

    def any_match(sample: str) -> bool:
        return any(rx.search(sample) for rx in compiled)

    for bad in ("%~q1", "%~q1%", "echo %~q1", "%~dq1", "%~b0"):
        assert any_match(bad), f"expected invalid pattern match for {bad!r}"
    # Letter-regex must not falsely flag these (including %~*, which is invalid
    # for a different reason — modifiers may not combine with %*).
    for spared_by_letter_regex in (
        "%~1",
        "%~dpnx0",
        "%~DPNX0",
        "%~F1",
        "%~A1",
        "%~FTZA1",
        "%~*",
        "%~$PATH:1",
        "%~ftza1",
        "%~dp0",
        "%~dp0log",
    ):
        assert not any_match(
            spared_by_letter_regex
        ), f"unexpected letter-regex match for {spared_by_letter_regex!r}"

    for bad_upper in ("%~Q1", "%~DQ1", "%~B0"):
        assert any_match(bad_upper), f"expected invalid pattern match for {bad_upper!r}"

    star_rules = [entry for entry in invalid if entry.get("modifiers") == "*"]
    assert star_rules, "expected invalid_combinations entry for %~ with %*"
    assert "may not be used with %*" in star_rules[0]["reason"]


def test_validate_rejects_invalid_yaml(tmp_path: Path) -> None:
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("builtin_commands: []\n", encoding="utf-8")
    schema_path = _paths.SCHEMA_DIR / "commands.schema.json"

    with pytest.raises(jsonschema.ValidationError):
        validate._validate_yaml(invalid_yaml, schema_path)


def test_validate_main_prints_success(capsys: pytest.CaptureFixture[str]) -> None:
    validate.main()
    captured = capsys.readouterr()
    assert "batch-spec validation passed" in captured.out
    assert "OK VERSION sync" in captured.out


def test_validate_version_sync_accepts_repo() -> None:
    validate._validate_version_sync()


def test_validate_version_sync_rejects_readme_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "VERSION").write_text("0.53.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "batch-spec"\nversion = "0.53.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "currently **0.52.0**\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit, match="README.md"):
        validate._validate_version_sync()


def test_validate_version_sync_rejects_pyproject_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "VERSION").write_text("0.53.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "batch-spec"\nversion = "0.52.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("currently **0.53.0**\n", encoding="utf-8")
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit, match="pyproject.toml version"):
        validate._validate_version_sync()


def test_validate_version_sync_rejects_missing_pyproject_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "VERSION").write_text("0.53.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "batch-spec"\n', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("currently **0.53.0**\n", encoding="utf-8")
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit, match="missing project version"):
        validate._validate_version_sync()


def test_validate_version_sync_rejects_bad_version_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "VERSION").write_text("not-a-version\n", encoding="utf-8")
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit, match="MAJOR.MINOR.PATCH"):
        validate._read_version_file()


def test_validate_version_sync_rejects_missing_readme_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "VERSION").write_text("0.53.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "batch-spec"\nversion = "0.53.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("no version marker\n", encoding="utf-8")
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit, match="version marker"):
        validate._validate_version_sync()


def test_validate_yaml_rejects_empty_document(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yaml"
    empty.write_text("\n", encoding="utf-8")
    schema_path = _paths.SCHEMA_DIR / "commands.schema.json"

    with pytest.raises(SystemExit, match="Empty YAML"):
        validate._validate_yaml(empty, schema_path)


def test_validate_json_rejects_invalid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    schema: dict[str, object] = {"type": "object"}

    with pytest.raises(SystemExit, match="Invalid JSON"):
        validate._validate_json(bad, schema)


def test_validate_corpus_rejects_unexpected_bom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus" / "parse"
    case = corpus / "bom-input"
    case.mkdir(parents=True)
    (case / "input.cmd").write_bytes(b"\xef\xbb\xbf@echo off\n")
    (case / "expect.json").write_text(
        '{"description": "bom", "parse": {"should_parse": true}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(validate, "CORPUS_DIR", corpus)
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        validate._validate_corpus()

    assert exc_info.value.code == 1


def test_check_utf8_c0_allows_listed_bom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)
    path = tmp_path / "utf8-bom-first-token-invalid" / "input.cmd"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xef\xbb\xbf@echo off\n")
    failures = validate._check_utf8_c0(path, allow_bom=True)
    assert not failures


def test_validate_corpus_rejects_empty_parse_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus" / "parse"
    case = corpus / "empty-parse"
    case.mkdir(parents=True)
    (case / "input.cmd").write_text("@echo off\n", encoding="utf-8")
    (case / "expect.json").write_text(
        '{"description": "empty parse", "parse": {}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(validate, "CORPUS_DIR", corpus)
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit, match="Schema validation failed"):
        validate._validate_corpus()


def test_validate_corpus_rejects_c0_in_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus" / "parse"
    case = corpus / "c0-input"
    case.mkdir(parents=True)
    (case / "input.cmd").write_bytes(b"@echo off\n\x0cecho hi\n")
    (case / "expect.json").write_text(
        '{"description": "c0", "parse": {"should_parse": true}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(validate, "CORPUS_DIR", corpus)
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        validate._validate_corpus()

    assert exc_info.value.code == 1


def test_validate_docs_encoding_rejects_c0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.md").write_bytes(b"# Title\nfor \x0cor\n")
    monkeypatch.setattr(validate, "DOCS_DIR", docs)
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        validate._validate_docs_encoding()

    assert exc_info.value.code == 1


def test_validate_docs_encoding_rejects_invalid_utf8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.md").write_bytes(b"# Title\n\xff\xfe invalid utf-8\n")
    monkeypatch.setattr(validate, "DOCS_DIR", docs)
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        validate._validate_docs_encoding()

    assert exc_info.value.code == 1


def test_validate_docs_encoding_accepts_real_docs() -> None:
    validate._validate_docs_encoding()


def test_validate_corpus_rejects_orphan_expect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus" / "parse"
    orphan = corpus / "orphan-expect"
    orphan.mkdir(parents=True)
    (orphan / "expect.json").write_text(
        '{"description": "orphan", "parse": {"should_parse": true}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(validate, "CORPUS_DIR", corpus)
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        validate._validate_corpus()

    assert exc_info.value.code == 1


def test_validate_corpus_rejects_orphan_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus" / "parse"
    orphan = corpus / "orphan-input"
    orphan.mkdir(parents=True)
    (orphan / "input.cmd").write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setattr(validate, "CORPUS_DIR", corpus)
    monkeypatch.setattr(validate, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        validate._validate_corpus()

    assert exc_info.value.code == 1


def test_grammar_fingerprint_is_deterministic() -> None:
    first = generate_parser._grammar_fingerprint()
    second = generate_parser._grammar_fingerprint()
    assert first == second
    assert len(first) == 64


def test_grammar_fingerprint_normalizes_crlf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    grammar_dir = tmp_path / "grammar"
    grammar_dir.mkdir()
    (grammar_dir / "BatchLexer.g4").write_bytes(b"lexer grammar BatchLexer;\r\n")
    (grammar_dir / "BatchParser.g4").write_bytes(b"parser grammar BatchParser;\r\n")
    monkeypatch.setattr(generate_parser, "GRAMMAR_DIR", grammar_dir)

    crlf_fingerprint = generate_parser._grammar_fingerprint()

    (grammar_dir / "BatchLexer.g4").write_bytes(b"lexer grammar BatchLexer;\n")
    (grammar_dir / "BatchParser.g4").write_bytes(b"parser grammar BatchParser;\n")

    lf_fingerprint = generate_parser._grammar_fingerprint()
    assert crlf_fingerprint == lf_fingerprint


def test_normalize_generated_source_strips_absolute_paths(tmp_path: Path) -> None:
    absolute = (
        b"# Generated from C:/Users/Laptop/repo/grammar/BatchLexer.g4 by ANTLR 4.13.2\n"
        b"from antlr4 import *\n"
    )
    relative = b"# Generated from BatchLexer.g4 by ANTLR 4.13.2\nfrom antlr4 import *\n"
    win_sep = (
        b"# Generated from D:\\a\\batch-spec\\grammar\\BatchLexer.g4 by ANTLR 4.13.2\n"
        b"from antlr4 import *\n"
    )
    assert generate_parser._normalize_generated_source(absolute) == relative
    assert generate_parser._normalize_generated_source(win_sep) == relative
    assert generate_parser._normalize_generated_source(relative) == relative

    abs_path = tmp_path / "BatchLexer.py"
    rel_path = tmp_path / "BatchLexerRel.py"
    abs_path.write_bytes(absolute)
    rel_path.write_bytes(relative)
    assert generate_parser._file_fingerprint(
        abs_path
    ) == generate_parser._file_fingerprint(rel_path)


def test_verified_antlr_jar_reuses_official_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cached jar with the official digest is not downloaded again."""
    jar_path = tmp_path / "antlr4-4.13.2-complete.jar"
    jar_path.write_bytes(b"cached")
    monkeypatch.setattr(generate_parser.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(
        generate_parser, "_jar_is_official", lambda payload: payload == b"cached"
    )

    def _unexpected_download() -> bytes:
        raise AssertionError("download")

    monkeypatch.setattr(generate_parser, "_download_antlr_jar", _unexpected_download)

    assert generate_parser.verified_antlr_jar() == jar_path


def test_verified_antlr_jar_stores_matching_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Matching bytes are written only after the digest check succeeds."""
    monkeypatch.setattr(generate_parser.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(generate_parser, "_download_antlr_jar", lambda: b"official")
    monkeypatch.setattr(
        generate_parser, "_jar_is_official", lambda payload: payload == b"official"
    )

    stored = generate_parser.verified_antlr_jar()

    assert stored.read_bytes() == b"official"


def test_download_antlr_jar_reads_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """The downloader returns the response body and does not run the jar."""

    class _Response:
        def read(self) -> bytes:
            return b"payload"

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    monkeypatch.setattr(
        generate_parser.urllib.request, "urlopen", lambda *_a, **_k: _Response()
    )

    assert generate_parser._download_antlr_jar() == b"payload"


def test_jar_checksum_rejects_unofficial_bytes() -> None:
    """A jar that is not the Maven Central artifact is not executed."""
    assert generate_parser._jar_is_official(b"not-the-antlr-jar") is False


def test_verified_antlr_jar_refuses_bad_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checksum mismatch raises before the bytes are saved or run."""
    monkeypatch.setattr(generate_parser.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(generate_parser, "_download_antlr_jar", lambda: b"bad-jar")

    with pytest.raises(SystemExit, match="does not match"):
        generate_parser.verified_antlr_jar()

    assert list(tmp_path.iterdir()) == []


def test_run_antlr_uses_relative_grammar_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    grammar_dir = tmp_path / "grammar"
    grammar_dir.mkdir()
    run_mock = MagicMock(return_value=MagicMock(returncode=0))
    jar_path = tmp_path / "antlr4-complete.jar"
    monkeypatch.setattr(generate_parser, "GRAMMAR_DIR", grammar_dir)
    monkeypatch.setattr(generate_parser, "verified_antlr_jar", lambda: jar_path)
    monkeypatch.setattr("generate_parser.subprocess.run", run_mock)

    generate_parser._run_antlr(tmp_path / "out")

    cmd = run_mock.call_args.args[0]
    assert cmd[:3] == ["java", "-jar", str(jar_path)]
    assert cmd[-2:] == ["BatchLexer.g4", "BatchParser.g4"]
    assert run_mock.call_args.kwargs["cwd"] == grammar_dir


def test_generate_parser_check_reports_missing_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_dir = tmp_path / "generated" / "python"
    generated_dir.mkdir(parents=True)
    monkeypatch.setattr(generate_parser, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(sys, "argv", ["generate_parser.py", "--check"])

    with pytest.raises(SystemExit) as exc_info:
        generate_parser.main()

    assert exc_info.value.code == 1


def test_generate_parser_check_reports_stale_stamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_dir = tmp_path / "generated" / "python"
    generated_dir.mkdir(parents=True)
    for name in (
        "BatchLexer.py",
        "BatchParser.py",
        "BatchParserVisitor.py",
        "__init__.py",
        ".grammar-stamp",
    ):
        (generated_dir / name).write_text("placeholder", encoding="utf-8")
    (generated_dir / ".grammar-stamp").write_text("stale", encoding="utf-8")

    monkeypatch.setattr(generate_parser, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(sys, "argv", ["generate_parser.py", "--check"])

    with pytest.raises(SystemExit) as exc_info:
        generate_parser.main()

    assert exc_info.value.code == 1


def test_generate_parser_check_passes_when_up_to_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_dir = tmp_path / "generated" / "python"
    generated_dir.mkdir(parents=True)
    fingerprint = generate_parser._grammar_fingerprint()
    init_text = '"""ANTLR-generated batch parser (do not edit by hand)."""\n'
    for name in ("BatchLexer.py", "BatchParser.py", "BatchParserVisitor.py"):
        (generated_dir / name).write_text("placeholder", encoding="utf-8")
    (generated_dir / "__init__.py").write_text(init_text, encoding="utf-8")
    (generated_dir / ".grammar-stamp").write_text(fingerprint, encoding="utf-8")

    def _fake_run_antlr(output_dir: Path) -> None:
        for name in ("BatchLexer.py", "BatchParser.py", "BatchParserVisitor.py"):
            (output_dir / name).write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(generate_parser, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(generate_parser, "_run_antlr", _fake_run_antlr)
    monkeypatch.setattr(sys, "argv", ["generate_parser.py", "--check"])

    generate_parser.main()


def test_generate_parser_check_reports_missing_antlr_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated_dir = tmp_path / "generated" / "python"
    generated_dir.mkdir(parents=True)
    fingerprint = generate_parser._grammar_fingerprint()
    init_text = '"""ANTLR-generated batch parser (do not edit by hand)."""\n'
    for name in ("BatchLexer.py", "BatchParser.py", "BatchParserVisitor.py"):
        (generated_dir / name).write_text("placeholder", encoding="utf-8")
    (generated_dir / "__init__.py").write_text(init_text, encoding="utf-8")
    (generated_dir / ".grammar-stamp").write_text(fingerprint, encoding="utf-8")

    def _fake_run_antlr(output_dir: Path) -> None:
        (output_dir / "BatchLexer.py").write_text("placeholder", encoding="utf-8")
        (output_dir / "BatchParser.py").write_text("placeholder", encoding="utf-8")
        # Intentionally omit BatchParserVisitor.py

    monkeypatch.setattr(generate_parser, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(generate_parser, "_run_antlr", _fake_run_antlr)
    monkeypatch.setattr(sys, "argv", ["generate_parser.py", "--check"])

    with pytest.raises(SystemExit) as exc_info:
        generate_parser.main()

    assert exc_info.value.code == 1
    assert "ANTLR did not produce BatchParserVisitor.py" in capsys.readouterr().err


def test_generate_parser_check_reports_file_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated_dir = tmp_path / "generated" / "python"
    generated_dir.mkdir(parents=True)
    fingerprint = generate_parser._grammar_fingerprint()
    init_text = '"""ANTLR-generated batch parser (do not edit by hand)."""\n'
    for name in ("BatchLexer.py", "BatchParser.py", "BatchParserVisitor.py"):
        (generated_dir / name).write_text("committed", encoding="utf-8")
    (generated_dir / "__init__.py").write_text(init_text, encoding="utf-8")
    (generated_dir / ".grammar-stamp").write_text(fingerprint, encoding="utf-8")

    def _fake_run_antlr(output_dir: Path) -> None:
        for name in ("BatchLexer.py", "BatchParser.py", "BatchParserVisitor.py"):
            (output_dir / name).write_text("fresh", encoding="utf-8")

    monkeypatch.setattr(generate_parser, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(generate_parser, "_run_antlr", _fake_run_antlr)
    monkeypatch.setattr(sys, "argv", ["generate_parser.py", "--check"])

    with pytest.raises(SystemExit) as exc_info:
        generate_parser.main()

    assert exc_info.value.code == 1
    assert "Generated file drift: BatchLexer.py" in capsys.readouterr().err


def test_generate_parser_writes_stamp_and_init(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_dir = tmp_path / "generated" / "python"
    generated_dir.mkdir(parents=True)
    (generated_dir / "stale.txt").write_text("remove me", encoding="utf-8")
    grammar_dir = tmp_path / "grammar"
    grammar_dir.mkdir()
    (grammar_dir / "BatchLexer.g4").write_text(
        "lexer grammar BatchLexer;\n", encoding="utf-8"
    )
    (grammar_dir / "BatchParser.g4").write_text(
        "parser grammar BatchParser;\noptions { tokenVocab=BatchLexer; }\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(generate_parser, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(generate_parser, "GRAMMAR_DIR", grammar_dir)
    monkeypatch.setattr(
        generate_parser, "verified_antlr_jar", lambda: tmp_path / "antlr.jar"
    )
    monkeypatch.setattr(
        "generate_parser.subprocess.run",
        MagicMock(return_value=MagicMock(returncode=0)),
    )

    generate_parser.generate_parser()

    assert not (generated_dir / "stale.txt").exists()
    assert (generated_dir / "__init__.py").is_file()
    stamp = (generated_dir / ".grammar-stamp").read_text(encoding="utf-8").strip()
    assert stamp == generate_parser._grammar_fingerprint()


def test_generate_parser_creates_missing_output_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_dir = tmp_path / "generated" / "python"
    assert not generated_dir.exists()
    grammar_dir = tmp_path / "grammar"
    grammar_dir.mkdir()
    (grammar_dir / "BatchLexer.g4").write_text(
        "lexer grammar BatchLexer;\n", encoding="utf-8"
    )
    (grammar_dir / "BatchParser.g4").write_text(
        "parser grammar BatchParser;\noptions { tokenVocab=BatchLexer; }\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(generate_parser, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(generate_parser, "GRAMMAR_DIR", grammar_dir)
    monkeypatch.setattr(
        generate_parser, "verified_antlr_jar", lambda: tmp_path / "antlr.jar"
    )
    monkeypatch.setattr(
        "generate_parser.subprocess.run",
        MagicMock(return_value=MagicMock(returncode=0)),
    )

    generate_parser.generate_parser()

    assert generated_dir.is_dir()
    assert (generated_dir / "__init__.py").is_file()
    stamp = (generated_dir / ".grammar-stamp").read_text(encoding="utf-8").strip()
    assert stamp == generate_parser._grammar_fingerprint()


def test_generate_parser_main_writes_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated_dir = tmp_path / "generated" / "python"
    monkeypatch.setattr(generate_parser, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(generate_parser, "generate_parser", MagicMock())
    monkeypatch.setattr(sys, "argv", ["generate_parser.py"])

    generate_parser.main()

    captured = capsys.readouterr()
    assert f"Wrote ANTLR output to {generated_dir}" in captured.out
