import json
import sqlite3
from datetime import datetime, timedelta, timezone

from agent_cli_sqlite.cli import main
from agent_cli_sqlite.storage import DEFAULT_TTL_SECONDS


def parse_iso(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_temporary_scope_gets_default_ttl(capsys, db_path):
    before = datetime.now(timezone.utc)
    code, out, err = run(capsys, "save", "--project", "p", "--key", "k", "--value", "v",
                         "--scope", "temporary")
    assert code == 0, err
    payload = json.loads(out)
    assert payload["scope"] == "temporary"
    expires = parse_iso(payload["expires_at"])
    assert timedelta(seconds=DEFAULT_TTL_SECONDS - 5) <= expires - before <= timedelta(seconds=DEFAULT_TTL_SECONDS + 5)


def test_explicit_ttl_is_applied(capsys, db_path):
    before = datetime.now(timezone.utc)
    code, out, _ = run(capsys, "save", "--project", "p", "--key", "k", "--value", "v",
                       "--scope", "temporary", "--ttl", "60")
    assert code == 0
    expires = parse_iso(json.loads(out)["expires_at"])
    assert timedelta(seconds=55) <= expires - before <= timedelta(seconds=65)


def test_ttl_with_persistent_scope_is_rejected(capsys, db_path):
    code, out, err = run(capsys, "save", "--project", "p", "--key", "k", "--value", "v",
                         "--scope", "persistent", "--ttl", "60")
    assert code == 2
    assert out == ""
    assert json.loads(err)["error"]["code"] == "validation_error"


def test_ttl_out_of_range_is_rejected(capsys, db_path):
    code, _, err = run(capsys, "save", "--project", "p", "--key", "k", "--value", "v",
                       "--scope", "temporary", "--ttl", "0")
    assert code == 2
    assert json.loads(err)["error"]["code"] == "validation_error"


def test_expired_record_is_hidden_but_stored(capsys, db_path):
    run(capsys, "save", "--project", "p", "--key", "k", "--value", "v", "--scope", "temporary", "--ttl", "60")
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE records SET expires_at = ?", ("2000-01-01T00:00:00Z",))
        conn.commit()

    code, out, err = run(capsys, "get", "--project", "p", "--key", "k")
    assert code == 3
    assert out == ""
    assert json.loads(err)["error"]["code"] == "not_found"

    code, out, _ = run(capsys, "search", "--project", "p", "--query", "v")
    assert json.loads(out)["count"] == 0

    code, out, _ = run(capsys, "list", "--project", "p")
    assert json.loads(out)["count"] == 0

    with sqlite3.connect(db_path) as conn:
        stored = conn.execute("SELECT COUNT(*) FROM records WHERE key = 'k'").fetchone()[0]
    assert stored == 1


def test_resave_refreshes_ttl(capsys, db_path):
    run(capsys, "save", "--project", "p", "--key", "k", "--value", "v", "--scope", "temporary", "--ttl", "60")
    code, out, _ = run(capsys, "save", "--project", "p", "--key", "k", "--value", "v2",
                       "--scope", "temporary", "--ttl", "3600")
    assert code == 0
    expires = parse_iso(json.loads(out)["expires_at"])
    assert expires > datetime.now(timezone.utc) + timedelta(seconds=3000)
