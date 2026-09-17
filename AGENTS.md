# AGENTS.md

Instructions for coding agents working on **batch-spec**.

## Project

Single source of truth for Windows batch/cmd.exe **language** structure used by
[Blinter](https://github.com/tboy1337/Blinter) and other conforming tools.

This repo defines grammar, expansion rules, and command catalogs. It does **not**
define linter rules (E/W/S/SEC/P codes) — those live in Blinter's `spec/` tree.

- License: AGPL-3.0-or-later (`COPYING`)
- Python: **3.12**, **3.13**, **3.14**
- Parser generation: ANTLR **4.13.2** (`antlr4-tools`)
- Package version: contents of `VERSION` (keep `README.md` and `pyproject.toml` aligned)

## Setup

```bash
pip install -r requirements-dev.txt
```

`requirements-dev.txt` includes `-r requirements.txt`.

## Commands

Full local gate (format, lint, types, validate, generate `--check`, pytest with
95% coverage on `scripts`/`conformance`, pip-audit, conformance):

```bash
python scripts/verify.py
```

Useful skips: `--skip-format`, `--skip-lint`, `--skip-types`, `--skip-conformance`,
`--skip-audit`.

Targeted:

```bash
python scripts/validate.py
python scripts/generate_parser.py
python scripts/generate_parser.py --check
python conformance/run_parser.py --impl antlr
python -m pytest --cov=scripts --cov=conformance --cov-fail-under=95
```

## Layout

| Path | Purpose |
|------|---------|
| `grammar/` | ANTLR 4 lexer/parser (`.g4`) |
| `data/commands.yaml` | Builtin, external, deprecated, removed commands and typos |
| `data/expansion.yaml` | `%` / `!` / `%~` expansion and related language semantics |
| `schema/` | JSON Schema for YAML and parse corpus |
| `audit/cmd-help/` | Captured `cmd.exe /?` reference text |
| `corpus/parse/` | Parser conformance fixtures |
| `conformance/` | Implementation-agnostic conformance runner |
| `generated/python/` | Generated ANTLR Python (do not hand-edit) |
| `scripts/` | Validation and parser generation |
| `docs/` | Consumer documentation for catalogs and corpus contract |
| `tests/` | Tooling / conformance / verify tests |

## Where truth lives

| Concern | Authority |
|---------|-----------|
| Syntax acceptance | `grammar/BatchLexer.g4`, `grammar/BatchParser.g4` |
| Expansion / language semantics | `data/expansion.yaml` |
| Command catalogs | `data/commands.yaml` |
| Parse fixture contract | `docs/parse-corpus.md` + `schema/parse-expect.schema.json` |
| Parse fixtures | `corpus/parse/<case-id>/{input.cmd,expect.json}` |

Regenerate `generated/python/` from the grammar; never edit those files by hand.

## Boundaries

**Always**

- After grammar, YAML, schema, or corpus changes, run validate + generate check +
  conformance (or full `python scripts/verify.py`).
- Keep each corpus case directory paired: both `input.cmd` and `expect.json`.
- Prefer fixture tags `redirection` and `quoting` (not `redirect` / `quotes`).
- Merge new tests into existing files under `tests/` (do not spawn near-duplicate
  test modules).

**Ask first**

- Bumping `VERSION` / release tagging
- Large grammar rewrites
- Registering a new conformance `--impl` backend

**Never**

- Invent language facts without live cmd evidence reflected in the corpus and/or
  catalogs (`data/expansion.yaml`, `data/commands.yaml`)
- Put Blinter linter rule codes in this repository
- Treat a directory name containing `invalid` as implying
  `expect_syntax_errors: true` (many `*-invalid` cases still `should_parse: true`;
  see `docs/parse-corpus.md`)
- Commit secrets or depend on untagged `main` in production consumer CI (pin a
  published `vMAJOR.MINOR.PATCH` tag)

## Common workflows

1. **Add a parse fixture**
   - Create `corpus/parse/<case-id>/` with `input.cmd` and `expect.json`
   - Follow `docs/parse-corpus.md` and `schema/parse-expect.schema.json`
   - Run `python scripts/validate.py` and
     `python conformance/run_parser.py --impl antlr`

2. **Change the grammar**
   - Edit `grammar/*.g4`
   - Run `python scripts/generate_parser.py`
   - Add or update corpus cases, then re-run conformance (or `verify.py`)

3. **Update catalogs**
   - Edit `data/commands.yaml` or `data/expansion.yaml` against the matching
     schema under `schema/`
   - Update `docs/commands-catalog.md` or `docs/expansion.md` when the
     consumer-facing contract changes
   - Run `python scripts/validate.py`

## Docs

- [Parse corpus contract](docs/parse-corpus.md)
- [Expansion catalog](docs/expansion.md)
- [Commands catalog](docs/commands-catalog.md)
- [README](README.md) (versioning and human overview)
