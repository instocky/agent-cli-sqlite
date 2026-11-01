"""Слой хранения: SQLite, только параметризованные запросы, без операций удаления.

Ошибки уровня БД не содержат путь к файлу и текст исключения sqlite3.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import resolve_db_path
from .schema import SchemaVersionError, init_schema

DEFAULT_TTL_SECONDS = 3600
MAX_TTL_SECONDS = 30 * 24 * 3600
DEFAULT_SEARCH_LIMIT = 50
DEFAULT_LIST_LIMIT = 100
MAX_LIMIT = 1000
SCOPES = ("temporary", "persistent")

_RECORD_COLUMNS = "id, project, key, value, scope, created_at, updated_at, expires_at"
_VISIBLE = "(expires_at IS NULL OR expires_at > ?)"


class StorageError(Exception):
    """БД недоступна, повреждена или заблокирована. Сообщение обезличено."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _row_to_record(row: sqlite3.Row) -> dict[str, Any]:
    return {column: row[column] for column in ("id", "project", "key", "value", "scope",
                                              "created_at", "updated_at", "expires_at")}


class Storage:
    """Доступ к записям. Удаление данных не предусмотрено."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path is not None else resolve_db_path()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path), timeout=5.0)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            init_schema(self._conn)
        except SchemaVersionError as exc:
            self.close()
            raise StorageError("database schema version is not supported") from exc
        except (sqlite3.Error, OSError) as exc:
            self.close()
            raise StorageError("database is unavailable or corrupted") from exc

    def close(self) -> None:
        conn = getattr(self, "_conn", None)
        if conn is not None:
            conn.close()
            self._conn = None  # type: ignore[assignment]

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def save(self, project: str, key: str, value: str, scope: str = "persistent",
             ttl: int | None = None) -> dict[str, Any]:
        """Создаёт запись или обновляет существующую по ключу (project, key)."""
        now = _utcnow()
        now_iso = _iso(now)
        expires_at = None
        if scope == "temporary":
            seconds = DEFAULT_TTL_SECONDS if ttl is None else ttl
            expires_at = _iso(now + timedelta(seconds=seconds))

        created = True
        try:
            with self._conn:
                row = self._conn.execute(
                    "SELECT id FROM records WHERE project = ? AND key = ?", (project, key)
                ).fetchone()
                if row is None:
                    try:
                        self._conn.execute(
                            "INSERT INTO records (project, key, value, scope, created_at, updated_at, expires_at)"
                            " VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (project, key, value, scope, now_iso, now_iso, expires_at),
                        )
                    except sqlite3.IntegrityError:
                        # Ключ занят параллельным процессом — переходим на обновление.
                        created = False
                        self._conn.execute(
                            "UPDATE records SET value = ?, scope = ?, updated_at = ?, expires_at = ?"
                            " WHERE project = ? AND key = ?",
                            (value, scope, now_iso, expires_at, project, key),
                        )
                else:
                    created = False
                    self._conn.execute(
                        "UPDATE records SET value = ?, scope = ?, updated_at = ?, expires_at = ?"
                        " WHERE project = ? AND key = ?",
                        (value, scope, now_iso, expires_at, project, key),
                    )
        except sqlite3.Error as exc:
            raise StorageError("failed to write record") from exc

        return {
            "project": project,
            "key": key,
            "scope": scope,
            "created": created,
            "expires_at": expires_at,
            "updated_at": now_iso,
        }

    def get(self, project: str, key: str) -> dict[str, Any] | None:
        """Возвращает запись или None (нет ключа / запись истекла)."""
        try:
            row = self._conn.execute(
                f"SELECT {_RECORD_COLUMNS} FROM records WHERE project = ? AND key = ? AND {_VISIBLE}",
                (project, key, _iso(_utcnow())),
            ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("failed to read record") from exc
        return _row_to_record(row) if row is not None else None

    def search(self, project: str, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> list[dict[str, Any]]:
        """Ищет по value и key в пределах проекта."""
        pattern = f"%{_escape_like(query)}%"
        try:
            rows = self._conn.execute(
                f"SELECT {_RECORD_COLUMNS} FROM records"
                f" WHERE project = ? AND {_VISIBLE}"
                " AND (value LIKE ? ESCAPE '\\' OR key LIKE ? ESCAPE '\\')"
                " ORDER BY updated_at DESC, id DESC LIMIT ?",
                (project, _iso(_utcnow()), pattern, pattern, limit),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("failed to search records") from exc
        return [_row_to_record(row) for row in rows]

    def list_records(self, project: str, limit: int = DEFAULT_LIST_LIMIT,
                     scope: str | None = None) -> list[dict[str, Any]]:
        """Список видимых записей проекта."""
        sql = f"SELECT {_RECORD_COLUMNS} FROM records WHERE project = ? AND {_VISIBLE}"
        params: list[Any] = [project, _iso(_utcnow())]
        if scope is not None:
            sql += " AND scope = ?"
            params.append(scope)
        sql += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params.append(limit)
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("failed to list records") from exc
        return [_row_to_record(row) for row in rows]
