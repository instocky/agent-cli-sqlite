import json
import sqlite3

from agent_cli_sqlite.cli import main


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


FORBIDDEN_COMMANDS = ("delete", "clear", "drop", "truncate", "reset", "update", "sql", "exec")


def test_no_delete_like_commands(capsys, db_path):
    for command in FORBIDDEN_COMMANDS:
        code, out, err = run(capsys, command)
        assert code == 2, f"{command} must not be available"
        assert out == ""
        assert json.loads(err)["error"]["code"] == "validation_error"


def test_raw_sql_passthrough_is_rejected(capsys, db_path):
    code, out, err = run(capsys, "save", "--project", "p", "--key", "k", "--value", "v",
                         "--sql", "DROP TABLE records")
    assert code == 2
    assert out == ""
    assert json.loads(err)["error"]["code"] == "validation_error"


def test_sql_injection_in_value_is_stored_literally(capsys, db_path):
    payload = "'; DROP TABLE records; --"
    code, _, err = run(capsys, "save", "--project", "p", "--key", "k", "--value", payload)
    assert code == 0, err

    with sqlite3.connect(db_path) as conn:
        stored = conn.execute("SELECT value FROM records WHERE key = 'k'").fetchone()[0]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert stored == payload
    assert "records" in tables


def test_storage_error_does_not_leak_path(capsys, db_path):
    db_path.write_bytes(b"this is not a sqlite database")
    code, out, err = run(capsys, "get", "--project", "p", "--key", "k")
    assert code == 4
    assert out == ""
    error = json.loads(err)["error"]
    assert error["code"] == "storage_error"
    assert str(db_path) not in err
    assert "sqlite" not in error["message"].lower()


def test_corrupted_database_is_not_reset(capsys, db_path):
    broken = b"this is not a sqlite database"
    db_path.write_bytes(broken)
    code, _, _ = run(capsys, "get", "--project", "p", "--key", "k")
    assert code == 4
    assert db_path.read_bytes() == broken


def test_save_does_not_leak_path_on_success(capsys, db_path):
    code, out, err = run(capsys, "save", "--project", "p", "--key", "k", "--value", "v")
    assert code == 0, err
    assert str(db_path) not in out
    assert str(db_path) not in err


def test_project_and_key_are_immutable_on_update(capsys, db_path):
    run(capsys, "save", "--project", "p", "--key", "k", "--value", "v1")
    code, out, _ = run(capsys, "save", "--project", "p", "--key", "k", "--value", "v2")
    assert code == 0
    payload = json.loads(out)
    assert payload["project"] == "p"
    assert payload["key"] == "k"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    assert rows == 1
