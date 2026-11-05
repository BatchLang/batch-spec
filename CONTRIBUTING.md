# Contributing to batch-spec

## Ways to Contribute

- Report bugs via [GitHub Issues](https://github.com/BatchLang/batch-spec/issues)
- Submit pull requests for grammar, catalogs, corpus fixtures, or tooling
- Improve the documents under `docs/`

Security issues must not be filed as public issues. See [SECURITY.md](SECURITY.md).
Lint findings (E/W/S/SEC/P codes) belong in
[Blinter](https://github.com/BatchLang/Blinter/issues).

## Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Install development dependencies: `uv sync --extra dev`
   (or `pip install -r requirements-dev.txt`).
3. Make the change. Grammar, catalog, schema, and corpus edits need matching
   fixtures or docs as described in [AGENTS.md](AGENTS.md).
4. Run `uv run python scripts/verify.py`. It needs `uv` and `java` on `PATH`.
5. Open a pull request against `main`.

Supported Python versions are 3.11, 3.12, 3.13, 3.14, and 3.15.

## Coding Standards

| Tool | Purpose |
| ---- | ------- |
| [Black](https://black.readthedocs.io/) | Python formatting (`line-length = 88`) |
| [isort](https://pycqa.github.io/isort/) | Import sorting (Black-compatible profile) |
| [autopep8](https://pypi.org/project/autopep8/) | Trailing whitespace only (W291, W293) |
| [pyproject-fmt](https://pyproject-fmt.readthedocs.io/) | `pyproject.toml` formatting |
| [mypy](https://mypy-lang.org/) | Static type checking (`strict` mode) |
| [pylint](https://pylint.readthedocs.io/) | Linting (`pylintrc`) |
| [yamllint](https://yamllint.readthedocs.io/) | YAML files (`.yamllint.yaml`) |
| [PyMarkdown](https://pymarkdown.readthedocs.io/) | Markdown files (`.pymarkdown.yaml`) |
| [bandit](https://bandit.readthedocs.io/) | Security linting for Python |
| [antlr-lint](https://pypi.org/project/antlr-v4-linter/) | ANTLR grammar under `grammar/` |

Auto-fix formatting before committing:

```bash
uv run python scripts/verify.py --fix
```

`--fix` rewrites trailing whitespace, import order, and `pyproject.toml`.
Black stays a check.

## Testing

Tests live in `tests/` and run from `scripts/verify.py` and from
`python -m pytest`. `pytest.ini` writes coverage reports and `tests/pytest.log`.
Parser conformance lives in `conformance/` and `corpus/parse/`.

CI runs `python scripts/verify.py --skip-pytest` once on Ubuntu (Python 3.14),
then pytest and conformance across Ubuntu, Windows, and macOS on Python
3.11–3.15. antlr-lint also runs on Windows with Python 3.11.

## License

By contributing, you agree that your contributions are licensed under [AGPL-3.0-or-later](COPYING).
