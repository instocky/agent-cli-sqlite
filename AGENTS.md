# AGENTS.md

Local SQLite-backed memory CLI for AI agents. One Python package, one SQLite file, one Agent Skill — no MCP, no HTTP API, no server.

## Setup commands

- Install deps: `pip install -e ".[dev]"` (or `uv venv .venv && uv pip install -e .`)
- Run CLI:     `agent-sqlite --help` (console script from `pyproject.toml` `[project.scripts]`)
- Test:        `python -m pytest -q`
- Lint:        `ruff check src tests`
- No CI configured yet — run test + lint locally before committing.

## Project layout

- `src/agent_cli_sqlite/` — package: `cli.py` (argparse contract), `storage.py` (SQLite layer), `schema.py` (DDL + schema version), `config.py` (DB path resolution)
- `skills/agent-cli-sqlite/SKILL.md` — Agent Skill, **source of truth** for agent-facing instructions
- `tests/` — `test_cli.py`, `test_storage.py`, `test_ttl.py`, `test_security.py`
- `docs/PRD.md` — the specification: CLI contract, data model, decisions, backlog

## Contracts you must not break

These are consumed by agents; changing them is a breaking change.

- Every command prints exactly one JSON object to stdout; errors print JSON to stderr with an empty stdout.
- Exit codes: `0` ok, `1` internal, `2` validation, `3` not found, `4` storage.
- `error.code` values are stable: `validation_error`, `not_found`, `storage_error`, `internal_error`.
- `save` is an upsert on `(project, key)`: `id` and `created_at` are preserved, `project`/`key` are immutable.
- Expired records are hidden from `get`/`search`/`list` but stay physically in the database.
- Every command requires `--project`; records never cross projects.

Any change here updates `docs/PRD.md`, `skills/agent-cli-sqlite/SKILL.md` and the tests in the same commit.

## Security invariants

- No delete path exists: never add `delete`/`clear`/`drop`/`truncate`/`reset`, never accept raw SQL.
- All SQL is parameterized; values are stored literally (no string interpolation into SQL).
- The database path is never printed to stdout/stderr and never appears in error messages.
- A corrupted database must produce `storage_error` — never reset, recreate, or overwrite the file.
- Never touch the SQLite file directly yourself; the CLI is the only interface.
- `AGENT_SQLITE_DB` overrides the path (tests only); the default lives in the platform data directory.

## Code style

- Python 3.12+, standard library only — runtime dependencies are not allowed (dev extra: pytest only).
- Type hints on public functions; module docstring on every module under `src/`.
- `ruff check src tests` must pass; keep lines roughly under 100 chars (E501 is not enforced by the default rule set).
- Keep the CLI contract in one place: `cli.py` validates, `storage.py` only touches SQLite.

## Testing instructions

- Unit tests: `python -m pytest -q` (pytest, `pythonpath = ["src"]` — no install needed to run them).
- Add tests for every new behavior next to the existing suites.
- Any change to the storage layer or CLI surface needs a `tests/test_security.py` case: no delete command, no SQL passthrough, no path leak, no reset of a corrupted DB.
- TTL semantics live in `tests/test_ttl.py`; upsert/isolation/search in `tests/test_storage.py`.

## PR & commit conventions

- Branch from `main`; never push to it directly. No remote is configured yet — ask before pushing.
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).
- Commit body: one bullet per file with the path and what changed, then `- Validation:`, `- Review:`, `- Time:` sections.
- `docs/PRD.md` is the source of truth for the spec — update it before or with the code change.
