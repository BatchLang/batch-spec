"""Tests for conformance/run_parser.py."""

# Private helpers are the subject of these tests; the rcfile cannot scope that check.
# pylint: disable=protected-access

from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

CONFORMANCE_DIR = Path(__file__).resolve().parent.parent / "conformance"
if str(CONFORMANCE_DIR) not in sys.path:
    sys.path.insert(0, str(CONFORMANCE_DIR))

import run_parser  # noqa: E402  # pylint: disable=wrong-import-position


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


def test_read_corpus_lines_keeps_utf8_bom(tmp_path: Path) -> None:
    """A leading BOM stays on the first line so the lexer can see it."""
    path = tmp_path / "input.cmd"
    path.write_bytes(b"\xef\xbb\xbf@echo off\n")

    lines = run_parser.read_corpus_lines(path)

    assert lines == ["\ufeff@echo off"]


def test_read_corpus_lines_keeps_bare_cr_inside_the_line(tmp_path: Path) -> None:
    """A CR that is not part of CRLF stays in the line so the lexer can drop it."""
    path = tmp_path / "input.cmd"
    path.write_bytes(b"@echo off\necho hello\rworld\n")

    lines = run_parser.read_corpus_lines(path)

    assert lines == ["@echo off", "echo hello\rworld"]


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
@pytest.mark.usefixtures("generated_parser")
def test_top_level_statement_helpers_with_real_tree() -> None:
    tree, errors = run_parser._parse_antlr(["if 1==1 echo yes"])
    assert tree is not None
    assert not errors
    assert run_parser._top_level_statement_name(tree) == "ifStmt"
    assert run_parser._top_level_statement_names(tree) == ["ifStmt"]


def _context_names(node: object) -> list[str]:
    names: list[str] = []
    stack: list[object] = [node]
    while stack:
        current = stack.pop()
        names.append(type(current).__name__)
        get_count = getattr(current, "getChildCount", None)
        get_child = getattr(current, "getChild", None)
        if not callable(get_count) or not callable(get_child):
            continue
        count = get_count()
        if not isinstance(count, int):
            continue
        for index in range(count):
            stack.append(get_child(index))
    return names


def _compare_operand_text(tree: object) -> list[str]:
    texts: list[str] = []
    stack: list[object] = [tree]
    while stack:
        current = stack.pop()
        if type(current).__name__ == "CompareOperandContext":
            get_text = getattr(current, "getText", None)
            texts.append(str(get_text()) if callable(get_text) else "")
        get_count = getattr(current, "getChildCount", None)
        get_child = getattr(current, "getChild", None)
        if not callable(get_count) or not callable(get_child):
            continue
        count = get_count()
        if not isinstance(count, int):
            continue
        for index in range(count - 1, -1, -1):
            stack.append(get_child(index))
    return texts


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_if_compare_operand_stops_before_then_command() -> None:
    """A space ends an IF compare operand. The then-command stays a command."""
    tree, errors = run_parser._parse_antlr(["if a==b echo hello world"])
    quoted, quoted_errors = run_parser._parse_antlr(['if "%1"=="" echo usage'])
    assert tree is not None and not errors
    assert quoted is not None and not quoted_errors
    assert _compare_operand_text(tree) == ["a", "b"]
    assert _compare_operand_text(quoted) == ['"%1"', '""']


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_double_quote_does_not_swallow_the_next_line() -> None:
    """An open quote ends at LF. The next physical line is its own command."""
    tree, errors = run_parser._parse_antlr(
        ["(", 'echo "hello', ")", 'echo "after"', "echo DONE"]
    )
    assert tree is not None and not errors
    assert run_parser._top_level_statement_names(tree) == [
        "groupStmt",
        "genericCmd",
        "genericCmd",
    ]


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_for_r_quoted_path_is_not_for_f_options() -> None:
    """A FOR /R root is a path even when it contains FOR /F option words."""
    tree, errors = run_parser._parse_antlr(
        ['for /r "D:\\eol files" %%f in (*.txt) do echo %%f']
    )
    tokens, token_errors = run_parser._parse_antlr(
        ['for /r "C:\\tokens" %%f in (*.txt) do echo %%f']
    )
    options, option_errors = run_parser._parse_antlr(
        ['for /f "tokens=1" %%f in (file.txt) do echo %%f']
    )
    bare, bare_errors = run_parser._parse_antlr(
        ["for /f %%f in (file.txt) do echo %%f"]
    )
    assert tree is not None and not errors
    assert tokens is not None and not token_errors
    assert options is not None and not option_errors
    assert bare is not None and not bare_errors
    assert run_parser._top_level_statement_name(tree) == "forStmt"
    assert run_parser._top_level_statement_name(options) == "forStmt"
    assert run_parser._top_level_statement_name(bare) == "forStmt"


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_call_inside_group_is_call_statement() -> None:
    """(call) is CALL. call) is not a keyword, and (if) is a syntax error."""
    grouped, grouped_errors = run_parser._parse_antlr(["(call)"])
    multiline, multiline_errors = run_parser._parse_antlr(["(", "call)"])
    glued, glued_errors = run_parser._parse_antlr(["call)"])
    bare_if, bare_if_errors = run_parser._parse_antlr(["(if)"])
    assert grouped is not None and not grouped_errors
    assert multiline is not None and not multiline_errors
    unclosed, unclosed_errors = run_parser._parse_antlr(
        ['echo "a', "(", 'echo "b', "call)"]
    )
    assert "CallStmtContext" in _context_names(grouped)
    assert "CallStmtContext" in _context_names(multiline)
    assert unclosed is not None and not unclosed_errors
    assert "CallStmtContext" in _context_names(unclosed)
    assert glued_errors
    assert "CallStmtContext" not in _context_names(glued)
    assert bare_if is not None and bare_if_errors


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_escaped_paren_does_not_change_group_depth() -> None:
    """A caret escapes one parenthesis. ^^) is a real closer. ^( is not an opener."""
    kept, kept_errors = run_parser._parse_antlr(["(", "echo ^)", "call)"])
    opened, opened_errors = run_parser._parse_antlr(["echo ^(", "call)"])
    closed, closed_errors = run_parser._parse_antlr(["(", "echo ^^)", "call)"])
    assert kept is not None and not kept_errors
    assert "CallStmtContext" in _context_names(kept)
    assert opened is not None and opened_errors
    assert "CallStmtContext" not in _context_names(opened)
    assert closed is not None and closed_errors
    assert "CallStmtContext" not in _context_names(closed)


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_parse_keeps_utf8_bom_on_the_first_token() -> None:
    tree, errors = run_parser._parse_antlr(["\ufeff@echo off"])
    assert tree is not None and not errors
    get_text = getattr(tree, "getText", None)
    assert callable(get_text)
    assert "\ufeff" in str(get_text())


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_top_level_statements_rem_absorption_vs_glue() -> None:
    absorbed, err_a = run_parser._parse_antlr(
        ["echo before&rem note & echo NO", "echo after"]
    )
    glued, err_g = run_parser._parse_antlr(
        ["echo before&rem) note & echo YES", "echo after"]
    )
    assert absorbed is not None and not err_a
    assert glued is not None and not err_g
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
@pytest.mark.usefixtures("generated_parser")
def test_top_level_ignores_nested_else_block_statements() -> None:
    tree, errors = run_parser._parse_antlr(["IF 1==1 (echo yes) ELSE (echo no)"])
    assert tree is not None
    assert not errors
    assert run_parser._top_level_statement_name(tree) == "ifStmt"
    nested = run_parser._collect_command_line_statements(tree)
    assert len(nested) > 1


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_check_case_top_level_statement_mismatch_with_real_tree(
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
@pytest.mark.usefixtures("generated_parser")
def test_check_case_top_level_statement_passes_with_real_tree(
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
    class _EmptyStatement:  # pylint: disable=too-few-public-methods
        children: list[object] | None = []

    assert run_parser._statement_rule_name(_EmptyStatement()) is None


def test_statement_rule_name_skips_nested_statement_context() -> None:
    class StatementContext:  # pylint: disable=too-few-public-methods
        """ANTLR StatementContext stand-in, which the helper skips."""

    class EchoStmtContext:  # pylint: disable=too-few-public-methods
        """Stand-in whose class name resolves to the echoStmt rule."""

    class _NestedStatement:  # pylint: disable=too-few-public-methods
        children: list[object] = [StatementContext(), EchoStmtContext()]

    assert run_parser._statement_rule_name(_NestedStatement()) == "echoStmt"


def test_statement_rule_name_returns_none_when_no_context_child() -> None:
    class _TokenOnly:  # pylint: disable=too-few-public-methods
        children: list[object] = [object(), "literal"]

    assert run_parser._statement_rule_name(_TokenOnly()) is None


def test_collect_command_line_ignores_non_statement_children() -> None:
    cmd = type("CommandLineContext", (), {})()
    cmd.children = [object(), "token"]
    assert not run_parser._collect_command_line_statements(cmd)


def test_collect_top_level_statements_handles_non_tree() -> None:
    assert not run_parser._collect_top_level_statements(object())


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

    assert not run_parser._collect_top_level_statements(tree)


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_set_punct_name_stays_single_setstmt() -> None:
    """Unquoted SET names with ~ @ # $ must not mid-line-split into genericCmd."""
    tree, errors = run_parser._parse_antlr(["set a~b=1", "set var@x=3", "set n#1=h"])
    assert tree is not None
    assert not errors
    statements = run_parser._collect_top_level_statements(tree)
    assert len(statements) == 3
    assert all(
        run_parser._statement_rule_name(stmt) == "setStmt" for stmt in statements
    )


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_hash_dollar_at_are_argument_tokens() -> None:
    tree, errors = run_parser._parse_antlr(
        ["echo #alone", "echo $alone", "echo hello@there"]
    )
    assert tree is not None
    assert not errors
    statements = run_parser._collect_top_level_statements(tree)
    assert len(statements) == 3
    assert all(
        run_parser._statement_rule_name(stmt) == "genericCmd" for stmt in statements
    )


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_parse_antlr_parses_simple_script() -> None:
    generated_dir = str(run_parser.GENERATED_DIR)
    if generated_dir in sys.path:
        sys.path.remove(generated_dir)

    tree, errors = run_parser._parse_antlr(["echo hello"])
    assert tree is not None
    assert not errors
    assert generated_dir in sys.path

    tree_again, errors_again = run_parser._parse_antlr(["echo bye"])
    assert tree_again is not None
    assert not errors_again


@pytest.mark.integration
@pytest.mark.usefixtures("generated_parser")
def test_parse_antlr_captures_syntax_errors() -> None:
    _tree, errors = run_parser._parse_antlr(["if"])
    assert errors
    assert any("line " in error for error in errors)


def test_main_runs_only_the_named_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sample_cases = [
        ("one", Path("a.cmd"), {"parse": {"should_parse": True}}),
        ("two", Path("b.cmd"), {"parse": {"should_parse": True}}),
    ]
    seen: list[str] = []

    def check(case_id: str, *_args: object, **_kwargs: object) -> None:
        seen.append(case_id)

    monkeypatch.setattr(run_parser, "_discover_cases", lambda: sample_cases)
    monkeypatch.setattr(run_parser, "_check_case", check)
    monkeypatch.setattr(
        sys, "argv", ["run_parser.py", "--impl", "antlr", "--case", "two"]
    )

    assert run_parser.main() == 0
    assert seen == ["two"]
    assert "All 1 parse cases passed" in capsys.readouterr().out


def test_main_rejects_an_unknown_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(run_parser, "_discover_cases", lambda: [])
    monkeypatch.setattr(
        sys, "argv", ["run_parser.py", "--impl", "antlr", "--case", "missing"]
    )

    assert run_parser.main() == 1
    assert "Unknown parse case: missing" in capsys.readouterr().err


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
