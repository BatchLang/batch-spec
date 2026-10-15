"""Tests for conformance/run_parser.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

CONFORMANCE_DIR = Path(__file__).resolve().parent.parent / "conformance"
if str(CONFORMANCE_DIR) not in sys.path:
    sys.path.insert(0, str(CONFORMANCE_DIR))

import run_parser  # noqa: E402


def _mock_impl(
    tree: object | None,
    errors: list[str],
) -> MagicMock:
    return MagicMock(return_value=(tree, errors))


def test_discover_cases_finds_repository_corpus() -> None:
    cases = run_parser._discover_cases()
    assert len(cases) > 0
    expect_paths = sorted(run_parser.CORPUS_DIR.glob("**/expect.json"))
    input_paths = sorted(run_parser.CORPUS_DIR.glob("**/input.cmd"))
    assert len(expect_paths) == len(input_paths) == len(cases)
    assert all(case_id for case_id, _, _ in cases)
    for expect_path in expect_paths:
        assert (expect_path.parent / "input.cmd").is_file()


def test_read_corpus_lines_keeps_cr_in_crlf_continuation(tmp_path: Path) -> None:
    """A caret before CRLF stays visible; splitlines() would have dropped the CR."""
    path = tmp_path / "input.cmd"
    path.write_bytes(b"@echo off\r\necho hello^\r\nworld\r\n")

    lines = run_parser.read_corpus_lines(path)

    assert lines == ["@echo off\r", "echo hello^\r", "world"]
    assert "\n".join(lines) == "@echo off\r\necho hello^\r\nworld"


def test_discover_cases_rejects_missing_input(
    tmp_corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_corpus / "missing-input"
    case_dir.mkdir()
    (case_dir / "expect.json").write_text(
        json.dumps({"description": "missing input", "parse": {"should_parse": True}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_parser, "CORPUS_DIR", tmp_corpus)

    with pytest.raises(SystemExit) as exc_info:
        run_parser._discover_cases()

    assert exc_info.value.code == 1


def test_check_case_success(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=object(), errors=[])
    message = run_parser._check_case(
        "ok-case",
        input_path,
        {"parse": {"should_parse": True}},
        impl,
    )
    assert message is None


def test_check_case_expect_syntax_errors_passes_with_errors(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=object(), errors=["line 1:0 error"])

    message = run_parser._check_case(
        "syntax-error-case",
        input_path,
        {"parse": {"expect_syntax_errors": True}},
        impl,
    )

    assert message is None


def test_check_case_expect_syntax_errors_fails_without_errors(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=object(), errors=[])

    message = run_parser._check_case(
        "syntax-error-case",
        input_path,
        {"parse": {"expect_syntax_errors": True}},
        impl,
    )

    assert message == "syntax-error-case: expected syntax errors, got none"


def test_check_case_should_parse_false_passes_with_errors(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=object(), errors=["line 1:0 error"])

    message = run_parser._check_case(
        "parse-failure-case",
        input_path,
        {"parse": {"should_parse": False}},
        impl,
    )

    assert message is None


def test_check_case_should_parse_false_fails_when_tree_present(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=object(), errors=[])

    message = run_parser._check_case(
        "parse-failure-case",
        input_path,
        {"parse": {"should_parse": False}},
        impl,
    )

    assert message == "parse-failure-case: expected parse failure"


def test_check_case_should_parse_fails_with_hidden_errors(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(
        tree=object(), errors=["line 1:0 token recognition error at: '@'"]
    )

    message = run_parser._check_case(
        "hidden-error-case",
        input_path,
        {"parse": {"should_parse": True}},
        impl,
    )

    assert message is not None
    assert "expected clean parse" in message


def test_check_case_missing_tree_reports_error(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=None, errors=[])

    message = run_parser._check_case(
        "missing-tree-case",
        input_path,
        {"parse": {"should_parse": True}},
        impl,
    )

    assert message == "missing-tree-case: parser returned no tree"


def test_check_case_non_dict_parse_meta_is_treated_as_empty(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=object(), errors=[])

    message = run_parser._check_case(
        "non-dict-meta",
        input_path,
        {"parse": "invalid"},
        impl,
    )

    assert message is None


def test_check_case_should_parse_false_passes_with_no_tree(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=None, errors=["line 1:0 error"])

    message = run_parser._check_case(
        "parse-failure-case",
        input_path,
        {"parse": {"should_parse": False}},
        impl,
    )

    assert message is None


def test_check_case_top_level_statement_mismatch(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=object(), errors=[])

    message = run_parser._check_case(
        "stmt-case",
        input_path,
        {"parse": {"top_level_statement": "ifStmt"}},
        impl,
    )

    assert message == "stmt-case: expected top-level statement 'ifStmt', got None"


def test_check_case_top_level_statements_mismatch(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=object(), errors=[])

    message = run_parser._check_case(
        "stmts-case",
        input_path,
        {"parse": {"top_level_statements": ["ifStmt", "genericCmd"]}},
        impl,
    )

    assert message == (
        "stmts-case: expected top-level statements ['ifStmt', 'genericCmd'], got []"
    )


def test_check_case_top_level_statements_rejects_non_strings(tmp_path: Path) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")
    impl = _mock_impl(tree=object(), errors=[])

    message = run_parser._check_case(
        "stmts-bad",
        input_path,
        {"parse": {"top_level_statements": ["genericCmd", 1]}},
        impl,
    )

    assert message == "stmts-bad: top_level_statements must be a non-empty string list"


@pytest.mark.integration
def test_top_level_statement_helpers_with_real_tree(
    generated_parser: None,
) -> None:
    tree, errors = run_parser._parse_antlr(["if 1==1 echo yes"])
    assert tree is not None
    assert errors == []
    assert run_parser._top_level_statement_name(tree) == "ifStmt"
    assert run_parser._top_level_statement_names(tree) == ["ifStmt"]


@pytest.mark.integration
def test_top_level_statements_rem_absorption_vs_glue(
    generated_parser: None,
) -> None:
    absorbed, err_a = run_parser._parse_antlr(
        ["echo before&rem note & echo NO", "echo after"]
    )
    glued, err_g = run_parser._parse_antlr(
        ["echo before&rem) note & echo YES", "echo after"]
    )
    assert absorbed is not None and err_a == []
    assert glued is not None and err_g == []
    assert run_parser._top_level_statement_names(absorbed) == [
        "genericCmd",
        "remStmt",
        "genericCmd",
    ]
    assert run_parser._top_level_statement_names(glued) == [
        "genericCmd",
        "genericCmd",
        "genericCmd",
        "genericCmd",
    ]


@pytest.mark.integration
def test_top_level_ignores_nested_else_block_statements(
    generated_parser: None,
) -> None:
    tree, errors = run_parser._parse_antlr(["IF 1==1 (echo yes) ELSE (echo no)"])
    assert tree is not None
    assert errors == []
    assert run_parser._top_level_statement_name(tree) == "ifStmt"
    nested = run_parser._collect_command_line_statements(tree)
    assert len(nested) > 1


@pytest.mark.integration
def test_check_case_top_level_statement_mismatch_with_real_tree(
    generated_parser: None,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("echo hi\n", encoding="utf-8")

    message = run_parser._check_case(
        "stmt-case",
        input_path,
        {"parse": {"top_level_statement": "ifStmt"}},
        run_parser._parse_antlr,
    )

    assert (
        message == "stmt-case: expected top-level statement 'ifStmt', got 'genericCmd'"
    )


@pytest.mark.integration
def test_check_case_top_level_statement_passes_with_real_tree(
    generated_parser: None,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.cmd"
    input_path.write_text("if 1==1 echo yes\n", encoding="utf-8")

    message = run_parser._check_case(
        "stmt-case",
        input_path,
        {"parse": {"top_level_statement": "ifStmt"}},
        run_parser._parse_antlr,
    )

    assert message is None


def test_statement_rule_name_returns_none_for_empty_children() -> None:
    class _EmptyStatement:
        children: list[object] | None = []

    assert run_parser._statement_rule_name(_EmptyStatement()) is None


def test_statement_rule_name_skips_nested_statement_context() -> None:
    class StatementContext:
        pass

    class EchoStmtContext:
        pass

    class _NestedStatement:
        children: list[object] = [StatementContext(), EchoStmtContext()]

    assert run_parser._statement_rule_name(_NestedStatement()) == "echoStmt"


def test_statement_rule_name_returns_none_when_no_context_child() -> None:
    class _TokenOnly:
        children: list[object] = [object(), "literal"]

    assert run_parser._statement_rule_name(_TokenOnly()) is None


def test_collect_command_line_ignores_non_statement_children() -> None:
    cmd = type("CommandLineContext", (), {})()
    cmd.children = [object(), "token"]
    assert run_parser._collect_command_line_statements(cmd) == []


def test_collect_top_level_statements_handles_non_tree() -> None:
    assert run_parser._collect_top_level_statements(object()) == []


def test_collect_top_level_skips_non_command_line_children() -> None:
    line = type(
        "LineContext",
        (),
        {
            "getChildCount": lambda self: 1,
            "getChild": lambda self, index: object(),
        },
    )()

    tree = type(
        "ScriptContext",
        (),
        {
            "getChildCount": lambda self: 1,
            "getChild": lambda self, index: line,
        },
    )()

    assert run_parser._collect_top_level_statements(tree) == []


@pytest.mark.integration
def test_set_punct_name_stays_single_setstmt(generated_parser: None) -> None:
    """Unquoted SET names with ~ @ # $ must not mid-line-split into genericCmd."""
    tree, errors = run_parser._parse_antlr(["set a~b=1", "set var@x=3", "set n#1=h"])
    assert tree is not None
    assert errors == []
    statements = run_parser._collect_top_level_statements(tree)
    assert len(statements) == 3
    assert all(
        run_parser._statement_rule_name(stmt) == "setStmt" for stmt in statements
    )


@pytest.mark.integration
def test_hash_dollar_at_are_argument_tokens(generated_parser: None) -> None:
    tree, errors = run_parser._parse_antlr(
        ["echo #alone", "echo $alone", "echo hello@there"]
    )
    assert tree is not None
    assert errors == []
    statements = run_parser._collect_top_level_statements(tree)
    assert len(statements) == 3
    assert all(
        run_parser._statement_rule_name(stmt) == "genericCmd" for stmt in statements
    )


@pytest.mark.integration
def test_parse_antlr_parses_simple_script(generated_parser: None) -> None:
    generated_dir = str(run_parser.GENERATED_DIR)
    if generated_dir in sys.path:
        sys.path.remove(generated_dir)

    tree, errors = run_parser._parse_antlr(["echo hello"])
    assert tree is not None
    assert errors == []
    assert generated_dir in sys.path

    tree_again, errors_again = run_parser._parse_antlr(["echo bye"])
    assert tree_again is not None
    assert errors_again == []


@pytest.mark.integration
def test_parse_antlr_captures_syntax_errors(generated_parser: None) -> None:
    _tree, errors = run_parser._parse_antlr(["if"])
    assert errors
    assert any("line " in error for error in errors)


def test_main_returns_zero_when_all_cases_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    sample_cases = [
        ("ok", Path("input.cmd"), {"parse": {"should_parse": True}}),
    ]
    monkeypatch.setattr(run_parser, "_discover_cases", lambda: sample_cases)
    monkeypatch.setattr(run_parser, "_check_case", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sys, "argv", ["run_parser.py", "--impl", "antlr"])

    assert run_parser.main() == 0


def test_main_returns_one_when_case_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sample_cases = [
        ("bad", Path("input.cmd"), {"parse": {"should_parse": True}}),
    ]
    monkeypatch.setattr(run_parser, "_discover_cases", lambda: sample_cases)
    monkeypatch.setattr(
        run_parser,
        "_check_case",
        lambda *_args, **_kwargs: "bad: parser returned no tree",
    )
    monkeypatch.setattr(sys, "argv", ["run_parser.py", "--impl", "antlr"])

    assert run_parser.main() == 1
    captured = capsys.readouterr()
    assert "bad: parser returned no tree" in captured.err
