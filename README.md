# batch-spec

Single source of truth for the Windows batch/cmd.exe **language** structure used by
[Blinter](https://github.com/BatchLang/Blinter) and other conforming tools.

This repository defines grammar, expansion rules, and command catalogs. It does **not**
define linter rules (E/W/S/SEC/P codes) -- those live in Blinter's `spec/` tree.

## Layout

| Path | Purpose |
|------|---------|
| `grammar/` | ANTLR 4 lexer/parser (`.g4`) |
| `data/commands.yaml` | Builtin, external, deprecated, removed commands and typos |
| `data/expansion.yaml` | `%` / `!` / `%~` expansion and related language semantics |
| `schema/` | JSON Schema for YAML and parse corpus |
| `audit/cmd-help/` | Captured `cmd.exe /?` reference text |
| `corpus/parse/` | Parser conformance fixtures (parse-only `expect.json`) |
| `conformance/` | Implementation-agnostic conformance runner |
| `scripts/` | Validation and parser generation |
| `docs/` | Consumer documentation for catalogs and corpus contract |

## Versioning

The package version is the contents of [`VERSION`](VERSION) (currently **0.72.7**). Releases are tagged `vMAJOR.MINOR.PATCH` matching that file. Pin a published tag (v0.68.0 and later) via git submodule or lock file. Do not depend on `main` in production CI.

## Validate

```bash
uv sync --extra dev
python scripts/validate.py
python scripts/generate_parser.py --check
python conformance/run_parser.py --impl antlr
```

`pip install -r requirements.txt` is the fallback when `uv` is not available.
`python scripts/generate_parser.py` rewrites `generated/python/`. `--check`
compares the committed parser to a fresh ANTLR run and does not write it.
Both commands need `java` on `PATH`. The script downloads the ANTLR **4.13.2**
complete jar from Maven Central and runs it only after the SHA-1 and SHA-256
match the published artifact. `conformance/run_parser.py --case <id>` checks
one corpus case.

## Local verification

Supported Python versions: **3.11**, **3.12**, **3.13**, **3.14**, and **3.15**.

The local gate formats and lints Python, YAML, Markdown, and `grammar/`,
type-checks, audits dependencies, runs tests at >=90% branch coverage of
`scripts` and `conformance`, and runs parser conformance.

```bash
uv sync --extra dev
uv run python scripts/verify.py
```

`pip install -r requirements-dev.txt` then `python scripts/verify.py` is the
fallback. `uv.lock` is the locked development environment. `verify.py` needs
`uv` and `java` on `PATH`.

Useful flags:

```bash
python scripts/verify.py --skip-format --skip-conformance --skip-audit
python scripts/verify.py --fix
python scripts/verify.py --skip-pytest
```

`--fix` rewrites trailing whitespace, import order, and `pyproject.toml`.
Black stays check-only. `--skip-pytest` is what CI's quality job runs; the
test matrix runs pytest and conformance on its own.

## Documentation

- [Parse corpus contract](docs/parse-corpus.md)
- [Expansion catalog](docs/expansion.md)
- [Commands catalog](docs/commands-catalog.md)

## Add a parser implementation

1. Implement parsing for all cases under `corpus/parse/`.
2. Register the implementation in `conformance/run_parser.py`.
3. Run `python conformance/run_parser.py --impl <name>` locally and in CI.

## License

AGPL-3.0-or-later -- see [COPYING](COPYING).
