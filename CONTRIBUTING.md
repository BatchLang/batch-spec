# Contributing to batch-spec

## Ways to Contribute

- Report bugs via [GitHub Issues](https://github.com/BatchLang/batch-spec/issues)
- Submit pull requests for grammar, catalogs, corpus fixtures, or tooling
- Improve the documents under `docs/`

Security issues must not be filed as public issues. See [SECURITY.md](SECURITY.md).

## Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Install development dependencies: `pip install -r requirements-dev.txt`
3. Make the change. Grammar, catalog, schema, and corpus edits need matching fixtures or docs as described in [AGENTS.md](AGENTS.md).
4. Run `python scripts/verify.py`.
5. Open a pull request against `main`.

Supported Python versions are 3.11, 3.12, 3.13, 3.14, and 3.15.

## Testing

Tests live in `tests/` and are part of `scripts/verify.py`, including format, pylint, mypy, and pytest. Parser conformance lives in `conformance/` and `corpus/parse/`.

## License

By contributing, you agree that your contributions are licensed under [AGPL-3.0-or-later](COPYING).
