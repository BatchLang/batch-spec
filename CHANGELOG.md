# Changelog

All notable changes to batch-spec are documented in this file. Release tags follow [Semantic Versioning](https://semver.org/).

## [0.72.1] - 2026-10-14

### Changed

- Consumers should pin a published tag. Tags from v0.68.0 onward already exist; do not depend on `main`
- The tag release workflow runs `scripts/verify.py` before it creates the GitHub release
- Pylint and mypy include `tests/`
- Added SECURITY.md, CONTRIBUTING.md, Dependabot configuration, and this changelog

[0.72.1]: https://github.com/BatchLang/batch-spec/releases/tag/v0.72.1
