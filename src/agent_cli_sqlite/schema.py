"""DDL и версия схемы БД."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS records (
        id         INTEGER PRIMARY KEY,
        project    TEXT NOT NULL,
        key        TEXT NOT NULL,
        value      TEXT NOT NULL,
        scope      TEXT NOT NULL CHECK (scope IN ('temporary', 'persistent')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT,
        UNIQUE (project, key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_records_project_updated ON records (project, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_records_expires ON records (expires_at)",
    "CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER NOT NULL)",
)


class SchemaVersionError(Exception):
    """Версия схемы в БД не совпадает с ожидаемой."""


def init_schema(conn: sqlite3.Connection) -> None:
    """Создаёт схему, если её нет. Не удаляет и не сбрасывает существующие данные."""
    with conn:
        for statement in _SCHEMA_STATEMENTS:
            conn.execute(statement)
        row = conn.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_meta (version) VALUES (?)", (SCHEMA_VERSION,))
        elif row[0] != SCHEMA_VERSION:
            raise SchemaVersionError(f"unsupported schema version: {row[0]}")
