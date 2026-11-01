# agent-cli-sqlite

Local memory storage for AI agents: one Python CLI, one SQLite database, one Agent Skill.
No MCP, no HTTP API, no server.

Design and decisions: [docs/PRD.md](docs/PRD.md).

## Install

```bash
pip install -e .
```

Runtime dependencies: none (Python 3.12+ standard library only).

## Usage

```bash
# Save (create or update by (project, key))
agent-sqlite save --project my-app --key architecture --value "FastAPI + SQLite" --scope persistent
agent-sqlite save --project my-app --key current_task --value "Implement auth" --scope temporary --ttl 3600

# Read
agent-sqlite get --project my-app --key architecture

# Search and list
agent-sqlite search --project my-app --query "FastAPI"
agent-sqlite list --project my-app
```

Every command prints exactly one JSON object to stdout. Errors print JSON to stderr and exit
non-zero (`2` validation, `3` not found, `4` storage).

## Guarantees

- **No deletion.** The CLI exposes no `delete`/`clear`/`drop`/`reset` and no raw SQL. Expired
  records are hidden from reads but stay in the database.
- **Project isolation.** Every command requires `--project`; records never cross projects.
- **Opaque path.** The database path is never printed in output or errors. It can be overridden
  with `AGENT_SQLITE_DB` (used by tests), otherwise it lives in the platform data directory.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Limitations

- Hiding the database path is not isolation: an agent with unrestricted shell access as the same
  OS user can still remove the file. Enforcing that requires a separate service account and OS
  permissions — tracked in PRD §10.1.
- No history of changes yet (FR-10), no vector search, no MCP/HTTP surface.
