---
name: agent-cli-sqlite
description: Use when you need to persist or recall context across sessions (architecture decisions, current task state, user preferences) via the agent-sqlite CLI. Read before storing anything in memory.
---

# agent-cli-sqlite

Persistent and temporary memory for agents. Storage is a local SQLite database; you access it
**only** through the `agent-sqlite` CLI.

## Rules

- Never open, edit, move, copy, or delete the SQLite file yourself. The CLI is the only
  interface. Do not search the filesystem for the database.
- Never attempt raw SQL, and never look for a `delete`/`drop`/`reset` command — they do not exist
  and must not be attempted.
- Deleting memory is impossible by design. If a fact is obsolete, overwrite the same key
  (`save` with the same `--project`/`--key` updates in place) and note the change in the value.

## Commands

```
agent-sqlite save   --project <p> --key <k> --value <text> [--scope persistent|temporary] [--ttl <seconds>]
agent-sqlite get    --project <p> --key <k>
agent-sqlite search --project <p> --query <text> [--limit N]
agent-sqlite list   --project <p> [--limit N] [--scope persistent|temporary]
```

Every command prints one JSON object to stdout. Errors print JSON to stderr and exit non-zero.

## Examples

Save a durable fact:

```bash
agent-sqlite save --project my-app --key architecture --value "FastAPI + SQLite" --scope persistent
# {"ok": true, "project": "my-app", "key": "architecture", "scope": "persistent",
#  "created": true, "expires_at": null, "updated_at": "2026-11-01T12:20:32Z"}
```

Save a fact that expires in two minutes (TTL is in seconds, `temporary` scope only):

```bash
agent-sqlite save --project my-app --key note --value "temporary note" --scope temporary --ttl 120
# {"ok": true, ..., "scope": "temporary", "created": true,
#  "expires_at": "2026-11-01T12:22:32Z", "updated_at": "2026-11-01T12:20:32Z"}
```

Update an existing key in place (`created` becomes `false`, `id` and `created_at` are kept):

```bash
agent-sqlite save --project my-app --key architecture --value "FastAPI + PostgreSQL" --scope persistent
# {"ok": true, ..., "created": false, ...}
```

Read a known key:

```bash
agent-sqlite get --project my-app --key architecture
# {"ok": true, "record": {"id": 1, "project": "my-app", "key": "architecture",
#  "value": "FastAPI + SQLite", "scope": "persistent",
#  "created_at": "...", "updated_at": "...", "expires_at": null}}
```

Search when you know the content but not the key:

```bash
agent-sqlite search --project my-app --query "FastAPI"
# {"ok": true, "query": "FastAPI", "count": 1, "records": [ ... ]}
```

List what the project already holds:

```bash
agent-sqlite list --project my-app
# {"ok": true, "count": 2, "records": [ ... ]}
```

Missing or expired key — exit code 3, empty stdout:

```bash
agent-sqlite get --project my-app --key note
# stderr: {"ok": false, "error": {"code": "not_found", "message": "key not found: note",
#          "details": {"project": "my-app", "key": "note"}}}
```

Bad argument — exit code 2:

```bash
agent-sqlite save --project my-app --key note --value "v" --scope persistent --ttl 60
# stderr: {"ok": false, "error": {"code": "validation_error",
#          "message": "ttl is only applicable to temporary scope", "details": {"field": "ttl"}}}
```

There is no delete command — do not try to invent one:

```bash
agent-sqlite delete --project my-app --key note
# stderr: {"ok": false, "error": {"code": "validation_error",
#          "message": "argument COMMAND: invalid choice: 'delete' (choose from save, get, search, list)"}}
```

## When to save

Save a record when the fact will still matter later: architecture or stack decisions, project
conventions, user preferences, long-running task state, and results of expensive investigation
that you would otherwise have to recompute.

Do not save: secrets or credentials, transient chatter, anything you can re-derive cheaply from
the repository, or anything the user did not ask you to remember.

## Choosing scope

- `persistent` — the fact stays until explicitly overwritten. Default.
- `temporary` — the fact expires automatically (`--ttl`, default 3600 seconds). Use it for
  "what am I doing right now" state that becomes worthless within the hour.

`--ttl` is only valid with `--scope temporary`; passing it with `persistent` is an error.

## Keys

Use short, stable, lowercase-dotted names: `architecture`, `db.schema`, `task.current`.
Allowed characters: letters, digits, `.`, `_`, `-`, `:` (max 128). Project identifiers use
letters, digits, `.`, `_`, `-` (max 64).

Keys are unique per project. Always pass the same `--project` for related facts.

## Reading

- `get` — exact key lookup. Use it when you know the key.
- `search` — substring match over values and keys, scoped to the project. Use it when you
  remember the content but not the key.
- `list` — overview of the project's records.

Read before writing: `get`/`search` first, then `save` to update instead of duplicating.

## Handling errors

| `error.code`       | Meaning                        | Action                                       |
| ------------------ | ------------------------------ | -------------------------------------------- |
| `validation_error` | Bad argument or format         | Fix the argument; do not retry unchanged     |
| `not_found`        | Key missing or expired         | Fall back to `search` or re-derive the fact  |
| `storage_error`    | Database unavailable/corrupted | Report to the user; do not attempt to repair |
| `internal_error`   | Unexpected failure             | Report to the user                           |

Never try to work around a `storage_error` by touching the database file directly.
