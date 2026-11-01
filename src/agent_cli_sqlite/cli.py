"""CLI-контракт: успех — JSON в stdout, ошибки — JSON в stderr.

Коды возврата: 0 ok, 1 internal_error, 2 validation_error, 3 not_found, 4 storage_error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Sequence

from .storage import (DEFAULT_LIST_LIMIT, DEFAULT_SEARCH_LIMIT, MAX_LIMIT, MAX_TTL_SECONDS,
                      SCOPES, Storage, StorageError)

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_VALIDATION = 2
EXIT_NOT_FOUND = 3
EXIT_STORAGE = 4

PROJECT_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

_PROG = "agent-sqlite"


class _UsageError(Exception):
    """Ошибка разбора аргументов."""


class _CliError(Exception):
    """Ошибка с готовым контрактом ответа."""

    def __init__(self, code: str, message: str, exit_code: int,
                 details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details or {}


class _JsonArgumentParser(argparse.ArgumentParser):
    """argparse, который сообщает об ошибках в JSON-формате контракта."""

    def error(self, message: str) -> None:  # noqa: D102 - argparse API
        raise _UsageError(message)


def _build_parser() -> _JsonArgumentParser:
    parser = _JsonArgumentParser(prog=_PROG, description="Local memory storage for AI agents.")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    save = subparsers.add_parser("save", help="Create or update a record.")
    save.add_argument("--project", required=True)
    save.add_argument("--key", required=True)
    save.add_argument("--value", required=True)
    save.add_argument("--scope", choices=SCOPES, default="persistent")
    save.add_argument("--ttl", type=int, default=None, help="TTL in seconds (temporary scope only).")

    get = subparsers.add_parser("get", help="Read a record by key.")
    get.add_argument("--project", required=True)
    get.add_argument("--key", required=True)

    search = subparsers.add_parser("search", help="Search records by content or key.")
    search.add_argument("--project", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=DEFAULT_SEARCH_LIMIT)

    listing = subparsers.add_parser("list", help="List records of a project.")
    listing.add_argument("--project", required=True)
    listing.add_argument("--limit", type=int, default=DEFAULT_LIST_LIMIT)
    listing.add_argument("--scope", choices=SCOPES, default=None)

    return parser


def _validate_project(project: str) -> None:
    if not PROJECT_PATTERN.match(project):
        raise _CliError("validation_error", f"invalid project identifier: {project!r}", EXIT_VALIDATION,
                        {"field": "project"})


def _validate_key(key: str) -> None:
    if not KEY_PATTERN.match(key):
        raise _CliError("validation_error", f"invalid key: {key!r}", EXIT_VALIDATION, {"field": "key"})


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_LIMIT:
        raise _CliError("validation_error", f"limit must be between 1 and {MAX_LIMIT}", EXIT_VALIDATION,
                        {"field": "limit"})


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "save":
        _validate_project(args.project)
        _validate_key(args.key)
        if not args.value:
            raise _CliError("validation_error", "value must not be empty", EXIT_VALIDATION,
                            {"field": "value"})
        if args.scope == "temporary":
            if args.ttl is not None and not 1 <= args.ttl <= MAX_TTL_SECONDS:
                raise _CliError("validation_error",
                                f"ttl must be between 1 and {MAX_TTL_SECONDS} seconds", EXIT_VALIDATION,
                                {"field": "ttl"})
        elif args.ttl is not None:
            raise _CliError("validation_error", "ttl is only applicable to temporary scope", EXIT_VALIDATION,
                            {"field": "ttl"})
        with Storage() as storage:
            return storage.save(args.project, args.key, args.value, args.scope, args.ttl)

    if args.command == "get":
        _validate_project(args.project)
        _validate_key(args.key)
        with Storage() as storage:
            record = storage.get(args.project, args.key)
        if record is None:
            raise _CliError("not_found", f"key not found: {args.key}", EXIT_NOT_FOUND,
                            {"project": args.project, "key": args.key})
        return {"record": record}

    if args.command == "search":
        _validate_project(args.project)
        if not args.query:
            raise _CliError("validation_error", "query must not be empty", EXIT_VALIDATION,
                            {"field": "query"})
        _validate_limit(args.limit)
        with Storage() as storage:
            records = storage.search(args.project, args.query, args.limit)
        return {"query": args.query, "count": len(records), "records": records}

    if args.command == "list":
        _validate_project(args.project)
        _validate_limit(args.limit)
        with Storage() as storage:
            records = storage.list_records(args.project, args.limit, args.scope)
        return {"count": len(records), "records": records}

    raise _CliError("validation_error", f"unknown command: {args.command}", EXIT_VALIDATION)


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"ok": True, **payload}) + "\n")


def _emit_error(code: str, message: str, details: dict[str, Any] | None = None) -> None:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    sys.stderr.write(json.dumps({"ok": False, "error": error}) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        payload = _dispatch(args)
    except _UsageError as exc:
        _emit_error("validation_error", str(exc))
        return EXIT_VALIDATION
    except _CliError as exc:
        _emit_error(exc.code, exc.message, exc.details)
        return exc.exit_code
    except StorageError as exc:
        _emit_error("storage_error", str(exc))
        return EXIT_STORAGE
    except Exception:  # noqa: BLE001 - наружу не выпускаем внутренние детали
        _emit_error("internal_error", "unexpected internal error")
        return EXIT_INTERNAL
    _emit(payload)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
