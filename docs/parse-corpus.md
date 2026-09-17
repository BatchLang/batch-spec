# Parse corpus contract

Each fixture lives under `corpus/parse/<case-id>/` and must contain both:

- `input.cmd` - UTF-8 batch source
- `expect.json` - expectations validated by `schema/parse-expect.schema.json`

`scripts/validate.py` fails if either file is missing for a case directory.

## expect.json fields

| Field | Required | Meaning |
|-------|----------|---------|
| description | yes | Human-readable case summary |
| parse | yes | Parse expectation object |
| tags | no | Free-form tags (`if`, `for`, `expansion`, `redirection`, `quoting`, ...) |

Prefer tag spelling `redirection` (not `redirect`) and `quoting` (not `quotes`)
for new fixtures.

### parse object

| Field | Meaning |
|-------|---------|
| should_parse | When true (or omitted with no error flags), require a clean parse tree and no syntax errors |
| should_parse: false | Pass only when the parse is not clean (errors and/or no usable tree) |
| expect_syntax_errors | Pass only when the implementation reports syntax errors |
| top_level_statement | Optional rule name of the **last script-level** statement (`ifStmt`, `forStmt`, `setStmt`, `genericCmd`, `detachedElseStmt`, ...). Nested statements inside IF/FOR/group blocks are ignored |
| top_level_statements | Optional ordered list of rule names for **all** script-level statements. Use when last-only is insufficient (for example REM absorption vs punctuation glue). Nested statements inside IF/FOR/group blocks are ignored |

`should_parse: true` must not be combined with `expect_syntax_errors: true`.
`should_parse: false` must not be combined with `expect_syntax_errors: true`.
Prefer `expect_syntax_errors` for constructs that live `cmd.exe` rejects with a
syntax / "was unexpected at this time" style failure (including leftover text
after an unquoted `)` that closes a parenthesized IF/FOR/naked group — see
[`data/expansion.yaml`](../data/expansion.yaml)
`command_chaining.close_paren_leftover_in_block`). Keep `should_parse: false`
available for implementations that fail without a clean tree.


## Scope

This corpus is **parse-structure** conformance aligned with live cmd syntax
rejection: when cmd reports a syntax error for the source as written, fixtures
should use `expect_syntax_errors: true` (for example empty unquoted IF operands
in `if-empty-unquoted-valid`, invalid `%~` letters in `e017-invalid-modifier`,
`%~*` in `percent-tilde-star-invalid`, or `IF EXISTS` misspelling).

Directory names containing `invalid` are not the same as
`expect_syntax_errors: true`. Some `*-invalid` fixtures still
`should_parse: true` and document semantic/runtime invalidity only (for example
sticky ERRORLEVEL, unknown external names, or a newline-detached ELSE that cmd
treats as an unknown command rather than an IF syntax abort — see
`else-newline-bare-invalid` / `else-unescaped-newline-invalid` and
`detachedElseStmt`). Runtime language facts that still parse cleanly (for example the
missing/empty substring form, or a UTF-8 BOM that prefixes the first token)
stay `should_parse: true` with guidance in
[`data/expansion.yaml`](../data/expansion.yaml).

Semantic rejection guidance (valid `%~` letters, SET /A rules, remarks, and
related facts) lives in [`data/expansion.yaml`](../data/expansion.yaml). Parser
acceptance does not imply catalog validity for purely semantic language facts.

**Structured SET /A and FOR /F options:** The ANTLR grammar parses `SET /A`
expressions as a typed expression tree (`setAExpr` and related rules) and
validates `FOR /F` option strings structurally for `eol=` (at most one
character), `skip=` (positive integer; zero rejected), `tokens=` (well-formed
positive indexes / ranges / `*`; zero indexes rejected), and `usebackq` /
`useback` (flag form). Both quoted `"options"` and unquoted caret-escaped
option text are validated. `delims=` is accepted as an option keyword but its
delimiter-character semantics are not structurally constrained by the grammar
(see [`data/expansion.yaml`](../data/expansion.yaml) `for_f.option_details.delims`).
A usebackq backtick `command` is a single `BACKTICK_STRING` token, so nested
parentheses and double quotes inside the backticks do not close `IN (` (see
`for-f-usebackq-nested-paren-command-valid`).
The grammar does require space/tab between `IN`/`DO`/`ELSE` and a following
`(` (live cmd rejects glued `in(` / `do(` / `else(`). IF may glue `(`
immediately after the IF keyword as a paren-wrapped predicate (`if(1==1)`,
usually silent-false); a true parenthesized then-body after a complete
predicate still needs space/tab before `(` (`if 1==1 (echo T)`, not
`if 1==1(echo T)`). Catalog notes also cover fileset member delimiters, non-expanding fileset
wildcards, `skip=` physical-line counting, duplicate `tokens=` indexes, FOR /F
ERRORLEVEL non-mutation, and input encoding. Expanded IF predicates such as
`if %b%` / `if not %b%` (when `b` holds `a==a` / `true==true`) are accepted as
`ifStmt` forms. Evaluation semantics (operator results, ERRORLEVEL codes,
empty-field collapse, bare-name truncation, and similar language facts) remain in
[`data/expansion.yaml`](../data/expansion.yaml). Unquoted `<<` and malformed
`FOR /F` option values that live cmd rejects are marked with
`expect_syntax_errors: true`. Other tool tails such as `START` remain largely
opaque token sequences unless live cmd reports a syntax error. Catalog notes
under `start_command` cover `/K` for batch/internal launches, `/B` ^C handling,
async-without-`/WAIT` races, `/D` / `/I`, and ERRORLEVEL 9059 launch failures. A command line
that ends with `(` (other than the `echo(` blank-line idiom) may be followed by
a multi-line `(...)` group that still parses and runs after the preceding
command — including the IF `and`/`or` orphan-block pattern documented in
[`data/expansion.yaml`](../data/expansion.yaml) `if_forms.no_and_or_keywords`.

Authoritative command syntax snippets for authors live under `audit/cmd-help/`.
