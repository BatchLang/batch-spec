#!/usr/bin/env python3

"""Run parser conformance cases against a registered implementation."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Callable, List

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# `as` marks an explicit re-export so mypy treats the name as part of this module.
# pylint: disable=useless-import-alias
from _paths import (  # noqa: E402  # pylint: disable=wrong-import-position
    CORPUS_DIR as CORPUS_DIR,
    GENERATED_DIR as GENERATED_DIR,
)

# pylint: enable=useless-import-alias

LOGGER = logging.getLogger(__name__)


def _discover_cases() -> list[tuple[str, Path, dict[str, object]]]:
    cases: list[tuple[str, Path, dict[str, object]]] = []
    orphan_expects: list[str] = []
    for expect_path in sorted(CORPUS_DIR.glob("**/expect.json")):
        case_dir = expect_path.parent
        input_path = case_dir / "input.cmd"
        case_id = "/".join(case_dir.relative_to(CORPUS_DIR).parts)
        if not input_path.is_file():
            orphan_expects.append(case_id)
            continue
        expect = json.loads(expect_path.read_text(encoding="utf-8"))
        cases.append((case_id, input_path, expect))
    if orphan_expects:
        for case_id in orphan_expects:
            message = f"Missing input.cmd for corpus case {case_id}"
            print(message, file=sys.stderr)
            LOGGER.error("%s", message)
        raise SystemExit(1)
    LOGGER.info("Discovered %s parse cases", len(cases))
    return cases


def _statement_rule_name(statement_ctx: object) -> str | None:
    children = getattr(statement_ctx, "children", None)
    if not children:
        return None
    for child in children:
        type_name = type(child).__name__
        if type_name == "StatementContext":
            continue
        if type_name.endswith("Context"):
            rule_name = type_name[: -len("Context")]
            return rule_name[0].lower() + rule_name[1:]
    return None


def _collect_command_line_statements(node: object) -> list[object]:
    """Collect Statement contexts under CommandLine nodes (includes nested blocks)."""
    statements: list[object] = []
    type_name = type(node).__name__
    if type_name == "CommandLineContext":
        for child in getattr(node, "children", None) or []:
            if type(child).__name__ == "StatementContext":
                statements.append(child)
    children = getattr(node, "children", None)
    if children:
        for child in children:
            statements.extend(_collect_command_line_statements(child))
    return statements


def _collect_top_level_statements(tree: object) -> list[object]:
    """Collect only script-level statements (not inside IF/FOR/group blocks)."""
    statements: list[object] = []
    get_child_count = getattr(tree, "getChildCount", None)
    get_child = getattr(tree, "getChild", None)
    if not callable(get_child_count) or not callable(get_child):
        return statements
    for i in range(get_child_count()):
        line = get_child(i)
        if type(line).__name__ != "LineContext":
            continue
        line_count = getattr(line, "getChildCount", lambda: 0)()
        line_child = getattr(line, "getChild")
        for j in range(line_count):
            child = line_child(j)
            if type(child).__name__ != "CommandLineContext":
                continue
            cmd_count = getattr(child, "getChildCount", lambda: 0)()
            cmd_child = getattr(child, "getChild")
            for k in range(cmd_count):
                stmt = cmd_child(k)
                if type(stmt).__name__ == "StatementContext":
                    statements.append(stmt)
    return statements


def _top_level_statement_name(tree: object) -> str | None:
    statements = _collect_top_level_statements(tree)
    if not statements:
        return None
    return _statement_rule_name(statements[-1])


def _top_level_statement_names(tree: object) -> list[str]:
    """Ordered rule names for all script-level statements."""
    names: list[str] = []
    for stmt in _collect_top_level_statements(tree):
        name = _statement_rule_name(stmt)
        if name is not None:
            names.append(name)
    return names


def _parse_antlr(lines: List[str]) -> tuple[object | None, list[str]]:
    # Generated modules are importable only after their directory is on sys.path.
    # pylint: disable=import-outside-toplevel
    if str(GENERATED_DIR) not in sys.path:
        sys.path.insert(0, str(GENERATED_DIR))

    from antlr4 import CommonTokenStream, InputStream  # isort: skip
    from antlr4.error.ErrorListener import ErrorListener  # isort: skip
    from BatchLexer import BatchLexer  # isort: skip
    from BatchParser import BatchParser  # isort: skip

    source = "\n".join(lines)
    lexer = BatchLexer(InputStream(source))
    token_stream = CommonTokenStream(lexer)
    parser = BatchParser(token_stream)
    errors: list[str] = []

    class _Listener(ErrorListener):  # type: ignore[misc, no-any-unimported]
        def syntaxError(  # pylint: disable=arguments-differ,too-many-positional-arguments
            self,
            recognizer: object,
            offendingSymbol: object,
            line: int,
            column: int,
            msg: str,
            e: BaseException | None,
        ) -> None:
            del recognizer, offendingSymbol, e
            errors.append(f"line {line}:{column} {msg}")

    lexer.removeErrorListeners()
    parser.removeErrorListeners()
    lexer.addErrorListener(_Listener())
    parser.addErrorListener(_Listener())
    tree = parser.script()
    return tree, errors


_IMPLEMENTATIONS: dict[str, Callable[[List[str]], tuple[object | None, list[str]]]] = {
    "antlr": _parse_antlr,
}


def _check_top_level_expectations(
    case_id: str,
    tree: object,
    parse_meta: dict[str, object],
) -> str | None:
    """Validate optional top_level_statement / top_level_statements expects."""
    expected_stmt = parse_meta.get("top_level_statement")
    if isinstance(expected_stmt, str) and expected_stmt:
        actual_stmt = _top_level_statement_name(tree)
        if actual_stmt != expected_stmt:
            return (
                f"{case_id}: expected top-level statement {expected_stmt!r}, "
                f"got {actual_stmt!r}"
            )

    expected_stmts = parse_meta.get("top_level_statements")
    if isinstance(expected_stmts, list) and expected_stmts:
        if not all(isinstance(item, str) and item for item in expected_stmts):
            return f"{case_id}: top_level_statements must be a non-empty string list"
        actual_stmts = _top_level_statement_names(tree)
        if actual_stmts != expected_stmts:
            return (
                f"{case_id}: expected top-level statements {expected_stmts!r}, "
                f"got {actual_stmts!r}"
            )
    return None


def read_corpus_lines(input_path: Path) -> list[str]:
    """Split on LF and keep a CR that belongs to a CRLF pair.

    ``str.splitlines()`` drops CR, so a caret that escapes the two-byte CRLF
    is indistinguishable from a caret before LF. The CR stays on the line and
    ``\\n``.join restores ``^\\r\\n`` for the lexer. A leading UTF-8 BOM stays
    in the first line so the lexer sees it as part of the first token.
    """
    data = input_path.read_bytes()
    text = data.decode("utf-8")
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    if parts and parts[-1].endswith("\r"):
        parts[-1] = parts[-1][:-1]
    return parts


def _check_case(
    case_id: str,
    input_path: Path,
    expect: dict[str, object],
    impl: Callable[[List[str]], tuple[object | None, list[str]]],
) -> str | None:
    lines = read_corpus_lines(input_path)
    tree, errors = impl(lines)
    parse_meta = expect.get("parse", {})
    if not isinstance(parse_meta, dict):
        parse_meta = {}

    if parse_meta.get("expect_syntax_errors"):
        return f"{case_id}: expected syntax errors, got none" if not errors else None

    if parse_meta.get("should_parse") is False:
        return (
            f"{case_id}: expected parse failure"
            if tree is not None and not errors
            else None
        )

    if tree is None:
        return f"{case_id}: parser returned no tree"

    if errors:
        return f"{case_id}: expected clean parse, got errors: {'; '.join(errors)}"

    return _check_top_level_expectations(case_id, tree, parse_meta)


def main() -> int:
    """Run the selected conformance implementation. Return 0 when every case passes."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="batch-spec parser conformance")
    parser.add_argument("--impl", default="antlr", choices=sorted(_IMPLEMENTATIONS))
    parser.add_argument(
        "--case",
        action="append",
        default=None,
        help="Run only this corpus case id. Repeat for more than one case.",
    )
    args = parser.parse_args()
    impl = _IMPLEMENTATIONS[args.impl]
    cases = _discover_cases()
    if args.case:
        wanted = set(args.case)
        known = {case_id for case_id, _input_path, _expect in cases}
        missing = sorted(wanted - known)
        if missing:
            for case_id in missing:
                print(f"Unknown parse case: {case_id}", file=sys.stderr)
                LOGGER.error("Unknown parse case: %s", case_id)
            return 1
        cases = [case for case in cases if case[0] in wanted]
    failures: list[str] = []
    for case_id, input_path, expect in cases:
        message = _check_case(case_id, input_path, expect, impl)
        if message:
            failures.append(message)
    if failures:
        for message in failures:
            print(message, file=sys.stderr)
            LOGGER.error("%s", message)
        return 1
    print(f"All {len(cases)} parse cases passed ({args.impl})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
