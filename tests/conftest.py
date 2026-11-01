import pytest


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Изолированная БД на каждый тест."""
    path = tmp_path / "memory.db"
    monkeypatch.setenv("AGENT_SQLITE_DB", str(path))
    return path


@pytest.fixture
def storage(db_path):
    from agent_cli_sqlite.storage import Storage

    with Storage() as instance:
        yield instance
