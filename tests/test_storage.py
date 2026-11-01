import sqlite3


def test_upsert_preserves_id_and_created_at(storage):
    first = storage.save("p", "k", "v1")
    record = storage.get("p", "k")
    storage.save("p", "k", "v2")
    updated = storage.get("p", "k")

    assert first["created"] is True
    assert updated["id"] == record["id"]
    assert updated["created_at"] == record["created_at"]
    assert updated["updated_at"] >= record["updated_at"]
    assert updated["value"] == "v2"


def test_project_isolation(storage):
    storage.save("project-a", "k", "a")
    storage.save("project-b", "k", "b")

    assert storage.get("project-a", "k")["value"] == "a"
    assert storage.get("project-b", "k")["value"] == "b"
    assert [r["value"] for r in storage.search("project-a", "k")] == ["a"]
    assert len(storage.list_records("project-a")) == 1


def test_list_is_scoped_and_sorted(storage):
    storage.save("p", "a", "1")
    storage.save("p", "b", "2")
    storage.save("p", "c", "3")

    records = storage.list_records("p")
    assert [r["key"] for r in records] == ["c", "b", "a"]
    assert len(storage.list_records("p", limit=2)) == 2


def test_list_filters_by_scope(storage):
    storage.save("p", "a", "1", scope="persistent")
    storage.save("p", "b", "2", scope="temporary", ttl=600)

    assert len(storage.list_records("p", scope="temporary")) == 1
    assert storage.list_records("p", scope="temporary")[0]["key"] == "b"
    assert len(storage.list_records("p")) == 2


def test_search_matches_value_and_key(storage):
    storage.save("p", "architecture", "FastAPI + SQLite")
    storage.save("p", "unrelated", "nothing here")

    assert len(storage.search("p", "FastAPI")) == 1
    assert len(storage.search("p", "architecture")) == 1
    assert storage.search("p", "absent") == []


def test_search_escapes_wildcards(storage):
    storage.save("p", "a", "100% done")
    storage.save("p", "b", "nothing")

    assert len(storage.search("p", "100%")) == 1
    assert len(storage.search("p", "%")) == 1


def test_schema_is_created_once(storage, db_path):
    storage.save("p", "k", "v")
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        version = conn.execute("SELECT version FROM schema_meta").fetchone()[0]
    assert rows == 1
    assert version == 1
