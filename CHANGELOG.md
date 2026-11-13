# Changelog

All notable changes to batch-spec are documented in this file. Release tags follow [Semantic Versioning](https://semver.org/).

## [0.72.7] - 2026-11-13

### Fixed

- `removed_commands` no longer lists `browstat`, `inuse`, or `streams`. Those names were never stock DOS or Windows commands. The key is only commands that shipped with DOS or Windows and are absent on modern cmd

## [0.72.6] - 2026-11-05

### Fixed

- Double quotes end at the physical line. An open quote does not swallow the next line or a later `)`
- An IF compare operand ends at a space or tab, so `if a==b echo hi` keeps `echo` as the then-command
- `FOR /F` option strings are recognized only after `/F`. A quoted `FOR /R` root such as `"D:\eol files"` is a path
- A keyword immediately before `)` stays that keyword when the `)` closes a group that is already open. `(call)` is `callStmt`. `(if)` is a syntax error. `call)` is not `CALL`. An unclosed quote does not hide a `(` on a later line, and a caret-escaped parenthesis (`^(` / `^)`) does not change that group
- The conformance reader keeps a leading UTF-8 BOM on the first line
- The invalid `%~` letter regex does not match a FOR form such as `%%~qf`
- Folded catalog notes store the quote and backslash characters they describe

### Changed

- `generate_parser.py` publishes the ANTLR jar with an atomic replace and runs `java -jar` on a private copy of the verified bytes. A cache that cannot be read or written does not stop generation. Generation needs a JDK on `PATH`
- `validate.py` prints each OK line once, on stdout
- `conformance/run_parser.py --case` runs one corpus case
- CI and tag releases both run from `.github/workflows/CI.yml`. A `v*` tag still waits for verification, and only that release job has `contents: write`. The notes come from `scripts/release_notes.py`

## [0.72.5] - 2026-11-05

### Fixed

- Label lookup keys end at space, tab, `+`, `:`, `&`, `|`, `<`, and `>`. `:ok:extra` is the key `ok`, and `goto :has other` matches the first `:has` line. Comma, semicolon, and equals stay inside a label line's key
- A caret inside a REM remark does not continue the line. A label or `::` line that ends in an odd caret does, and the joined physical lines are part of that label or remark

## [0.72.4] - 2026-10-21

### Fixed

- A CR that is not the CR of a CRLF pair is not a line break. The lexer drops it, and a remark or label still runs to LF. `^` plus CRLF remains one escaped line ending

## [0.72.3] - 2026-10-18

### Changed

- Supported Python versions are 3.11, 3.12, 3.13, 3.14, and 3.15
- The verification coverage gate is 90% on `scripts` and `conformance`
- Pylint runs in one process so the Python 3.15 job does not depend on dill serializing code objects

## [0.72.2] - 2026-10-15

### Changed

- CI pins `actions/checkout` and `actions/setup-python` by commit, and the tag workflow grants `contents: write` only to the release job
- `antlr4-python3-runtime` is pinned to 4.13.2. Parser generation runs `java -jar` only after the downloaded ANTLR complete jar matches the Maven Central digest
- `corpus/**` is marked `-text`, and the conformance reader keeps CR from CRLF fixtures

## [0.72.1] - 2026-10-14

### Changed

- Consumers should pin a published tag. Tags from v0.68.0 onward already exist; do not depend on `main`
- The tag release workflow runs `scripts/verify.py` before it creates the GitHub release
- Pylint and mypy include `tests/`
- Added SECURITY.md, CONTRIBUTING.md, Dependabot configuration, and this changelog

[0.72.7]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.7
[0.72.6]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.6
[0.72.5]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.5
[0.72.4]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.4
[0.72.3]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.3
[0.72.2]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.2
[0.72.1]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.1
