"""Конфигурация: путь к БД.

Путь никогда не попадает в stdout/stderr — только используется для подключения.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_DB_PATH = "AGENT_SQLITE_DB"
APP_DIR_NAME = "agent-cli-sqlite"
DB_FILE_NAME = "memory.db"


def resolve_db_path() -> Path:
    """Путь к файлу БД.

    Переопределяется env `AGENT_SQLITE_DB` (используется в тестах), иначе —
    пользовательский каталог данных платформы.
    """
    override = os.environ.get(ENV_DB_PATH)
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME / DB_FILE_NAME
