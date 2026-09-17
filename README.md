# batch-spec

Single source of truth for the Windows batch/cmd.exe **language** structure used by
[Blinter](https://github.com/tboy1337/Blinter) and other conforming tools.

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

The package version is the contents of [`VERSION`](VERSION) (currently **0.71.0**). Releases are intended to be tagged `vMAJOR.MINOR.PATCH` matching that file. Pin a
published tag via git submodule or lock file once it exists; do not depend on `main`
directly in production CI.

## Validate

```bash
pip install -r requirements.txt
python scripts/validate.py
python scripts/generate_parser.py
python conformance/run_parser.py --impl antlr
```

Parser generation uses ANTLR **4.13.2** (`antlr4-tools`).

## Local verification

Supported Python versions: **3.12**, **3.13**, and **3.14**.

For linting, type checking, tests (>=95% coverage), pip-audit, and conformance:

```bash
pip install -r requirements-dev.txt
python scripts/verify.py
```

Useful flags:

```bash
python scripts/verify.py --skip-format --skip-conformance --skip-audit
```

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

