# Changelog

All notable changes to batch-spec are documented in this file. Release tags follow [Semantic Versioning](https://semver.org/).

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

[0.72.4]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.4
[0.72.3]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.3
[0.72.2]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.2
[0.72.1]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.1
