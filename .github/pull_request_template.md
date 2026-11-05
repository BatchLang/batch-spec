## Summary

<!-- What does this change do, and why? Keep it to a few sentences. -->

## Type of change

<!-- Tick all that apply. -->

- [ ] Bug fix (grammar, catalog, or corpus disagrees with cmd.exe)
- [ ] Grammar change
- [ ] Catalog change (`data/commands.yaml` or `data/expansion.yaml`)
- [ ] Parse corpus fixture
- [ ] Tooling, CI, or developer configuration
- [ ] Documentation only
- [ ] Refactor or tests only (no language or behavior change)

## How was this tested?

<!-- Commands you ran, and the batch sample that shows the fix when this is a language change. -->

## Checklist

- [ ] I ran `uv run python scripts/verify.py` and it passes. It needs `uv` and `java` on `PATH`.
- [ ] I added or updated tests under `tests/`, extending an existing file.
- [ ] I did not bump `VERSION`, `pyproject.toml`, or the README version marker unless this pull request is a release.
- [ ] I did not edit `generated/python/` by hand. Parser changes come from `python scripts/generate_parser.py`.
- [ ] I did not put Blinter lint rule codes (E/W/S/SEC/P) in this repository.
- [ ] Corpus fixtures keep both `input.cmd` and `expect.json`, and I did not normalize line endings under `corpus/` (those paths are `-text` on purpose).
- [ ] My commit messages are clear and imperative.
- [ ] I have the right to contribute this code, and I agree it is licensed under AGPL-3.0-or-later.

## Grammar, catalog, or corpus

<!-- Delete this section if you did not change grammar/, data/, schema/, or corpus/. -->

- [ ] The change matches live cmd.exe behavior, and the corpus or catalog records that evidence.
- [ ] `python scripts/validate.py` and `python conformance/run_parser.py --impl antlr` pass.
- [ ] A grammar change regenerated `generated/python/` and `python scripts/generate_parser.py --check` passes.

## Notes for reviewers

<!-- Trade-offs, follow-ups, or platforms you could not test. -->
