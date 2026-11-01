import json

from agent_cli_sqlite.cli import main


def run(capsys, *argv):
    """Запускает CLI в процессе теста: (exit_code, stdout, stderr)."""
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_save_get_roundtrip(capsys, db_path):
    code, out, err = run(capsys, "save", "--project", "my-app", "--key", "architecture",
                         "--value", "FastAPI + SQLite")
    assert code == 0, err
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["created"] is True
    assert payload["expires_at"] is None

    code, out, _ = run(capsys, "get", "--project", "my-app", "--key", "architecture")
    assert code == 0
    record = json.loads(out)["record"]
    assert record["value"] == "FastAPI + SQLite"
    assert record["scope"] == "persistent"
    assert record["id"] > 0


def test_resave_updates_in_place(capsys, db_path):
    run(capsys, "save", "--project", "my-app", "--key", "k", "--value", "v1")
    code, out, _ = run(capsys, "save", "--project", "my-app", "--key", "k", "--value", "v2")
    assert code == 0
    assert json.loads(out)["created"] is False

    code, out, _ = run(capsys, "get", "--project", "my-app", "--key", "k")
    assert json.loads(out)["record"]["value"] == "v2"


def test_search_and_list(capsys, db_path):
    run(capsys, "save", "--project", "my-app", "--key", "architecture", "--value", "FastAPI + SQLite")
    run(capsys, "save", "--project", "my-app", "--key", "other", "--value", "unrelated")

    code, out, _ = run(capsys, "search", "--project", "my-app", "--query", "FastAPI")
    assert code == 0
    payload = json.loads(out)
    assert payload["count"] == 1
    assert payload["records"][0]["key"] == "architecture"

    code, out, _ = run(capsys, "list", "--project", "my-app")
    assert code == 0
    assert json.loads(out)["count"] == 2


def test_missing_key_returns_not_found(capsys, db_path):
    code, out, err = run(capsys, "get", "--project", "my-app", "--key", "absent")
    assert code == 3
    assert out == ""
    error = json.loads(err)["error"]
    assert error["code"] == "not_found"
    assert error["details"]["key"] == "absent"


def test_invalid_project_returns_validation_error(capsys, db_path):
    code, out, err = run(capsys, "get", "--project", "bad project!", "--key", "k")
    assert code == 2
    assert out == ""
    assert json.loads(err)["error"]["code"] == "validation_error"


def test_stdout_contains_single_json_object(capsys, db_path):
    code, out, _ = run(capsys, "save", "--project", "p", "--key", "k", "--value", "v")
    assert code == 0
    assert out.count("\n") == 1
    json.loads(out)
