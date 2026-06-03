# Contributing

> **English** · [한국어](CONTRIBUTING.ko.md)

Thanks for contributing to ArcSolve-Kit. The single source of truth for working rules
is [AGENTS.md](AGENTS.md).

## Dev setup

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest -q          # tests
uv run ruff check .       # lint
```

## Adding a new service

Follow the procedure in [docs/adding-a-service.md](docs/adding-a-service.md). Summary:

1. `arcsolve/services/<name>/` with `contract.py` + `tools.py` + `__init__.py` + `README.md`
2. `tests/test_<name>_contract.py` (contract validation, no network)
3. `changelog.d/<name>.md` (one-line change summary)
4. **Don't touch the registry** — dropping in a folder auto-discovers it.

## PR checklist

- [ ] `uv run pytest -q` passes
- [ ] `uv run ruff check .` passes
- [ ] Every field in the contract (`contract.py`) is confirmed against an official-doc
      link (no hallucinations; mark anything unconfirmed with `# TODO(provenance)`)
- [ ] The service README includes "Contract sources" official-doc links
- [ ] No new dependency added in the service folder (if needed, note it in the PR
      description → reflected in `pyproject.toml` at integration)
- [ ] (automated) CI regenerates `catalog`/`changelog` and checks there is no drift

## Docs language (i18n)

Docs are bilingual — **English is canonical**, Korean (`*.ko.md`) is a translation.
When you change a canonical file, update its `*.ko.md` in the same change or leave it
for the maintainer/Codex to refresh. See [docs/i18n.md](docs/i18n.md).

## Commits / branches

- Don't work directly on the default branch — cut a branch.
- Keep each PR narrow: one service/concern.
