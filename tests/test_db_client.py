import sqlite3

import pytest

from cookdex.db_client import MealieDBClient

# A slice of the Mealie v3.28 schema covering every table that references a
# recipe's ingredients or instructions.  None of these foreign keys cascade.
_SCHEMA_V328 = """
CREATE TABLE recipes (id CHAR(32) PRIMARY KEY, slug VARCHAR, name VARCHAR);
CREATE TABLE users (id CHAR(32) PRIMARY KEY, owned_recipes_id CHAR(32) REFERENCES recipes (id));
CREATE TABLE recipes_ingredients (
    id INTEGER PRIMARY KEY,
    recipe_id CHAR(32) REFERENCES recipes (id),
    referenced_recipe_id CHAR(32) REFERENCES recipes (id),
    note VARCHAR
);
CREATE TABLE recipes_ingredients_substitutions (
    id CHAR(32) PRIMARY KEY,
    ingredient_id INTEGER NOT NULL REFERENCES recipes_ingredients (id)
);
CREATE TABLE recipe_instructions (id CHAR(32) PRIMARY KEY, recipe_id CHAR(32) REFERENCES recipes (id));
CREATE TABLE recipe_ingredient_ref_link (
    id INTEGER PRIMARY KEY,
    instruction_id CHAR(32) REFERENCES recipe_instructions (id)
);
CREATE TABLE recipe_note_ref_link (
    id INTEGER PRIMARY KEY,
    instruction_id CHAR(32) REFERENCES recipe_instructions (id)
);
CREATE TABLE notes (id INTEGER PRIMARY KEY, recipe_id CHAR(32) REFERENCES recipes (id));
"""


def _client(monkeypatch, tmp_path, schema):
    path = tmp_path / "mealie.db"
    conn = sqlite3.connect(path)
    conn.executescript(schema)
    conn.executescript(
        """
        INSERT INTO recipes VALUES ('r1', 'soup', 'Soup'), ('r2', 'bread', 'Bread');
        INSERT INTO recipes_ingredients VALUES (1, 'r1', NULL, NULL), (2, 'r2', NULL, NULL);
        INSERT INTO recipe_instructions VALUES ('i1', 'r1'), ('i2', 'r2');
        INSERT INTO recipe_ingredient_ref_link VALUES (1, 'i1'), (2, 'i2');
        INSERT INTO notes VALUES (1, 'r1');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("MEALIE_DB_TYPE", "sqlite")
    monkeypatch.setenv("MEALIE_SQLITE_PATH", str(path))
    client = MealieDBClient()
    # Enforce foreign keys the way PostgreSQL does.
    client._db.conn.execute("PRAGMA foreign_keys = ON")
    return client


def _count(client, table):
    return client._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_delete_recipe_clears_v326_substitution_and_note_links(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, _SCHEMA_V328)
    client._db.execute("INSERT INTO recipes_ingredients_substitutions VALUES ('s1', 1), ('s2', 2)")
    client._db.execute("INSERT INTO recipe_note_ref_link VALUES (1, 'i1'), (2, 'i2')")
    client._db.commit()

    assert client.delete_recipe("soup") is True

    assert _count(client, "recipes") == 1
    # Only the other recipe's rows remain.
    assert _count(client, "recipes_ingredients_substitutions") == 1
    assert _count(client, "recipe_note_ref_link") == 1
    assert _count(client, "recipe_ingredient_ref_link") == 1
    assert _count(client, "recipes_ingredients") == 1
    client.close()


def test_delete_recipe_keeps_other_recipes_sub_recipe_lines(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, _SCHEMA_V328)
    # Bread uses soup as a sub-recipe twice, once with its own note.
    client._db.execute("INSERT INTO recipes_ingredients VALUES (3, 'r2', 'r1', ''), (4, 'r2', 'r1', 'for dipping')")
    client._db.execute("INSERT INTO recipes_ingredients_substitutions VALUES ('s3', 3)")
    client._db.execute("INSERT INTO users VALUES ('u1', 'r1')")
    client._db.commit()

    assert client.delete_recipe("soup") is True

    rows = client._db.execute(
        "SELECT id, recipe_id, referenced_recipe_id, note FROM recipes_ingredients ORDER BY id"
    ).fetchall()
    assert rows == [(2, "r2", None, None), (3, "r2", None, "Soup"), (4, "r2", None, "for dipping")]
    assert _count(client, "recipes_ingredients_substitutions") == 1
    assert client._db.execute("SELECT owned_recipes_id FROM users").fetchone() == (None,)
    client.close()


def test_delete_recipe_skips_tables_missing_on_older_mealie(monkeypatch, tmp_path):
    schema = _SCHEMA_V328.split("CREATE TABLE recipes_ingredients_substitutions")[0]
    schema += """
    CREATE TABLE recipe_instructions (id CHAR(32) PRIMARY KEY, recipe_id CHAR(32) REFERENCES recipes (id));
    CREATE TABLE recipe_ingredient_ref_link (
        id INTEGER PRIMARY KEY,
        instruction_id CHAR(32) REFERENCES recipe_instructions (id)
    );
    CREATE TABLE notes (id INTEGER PRIMARY KEY, recipe_id CHAR(32) REFERENCES recipes (id));
    """
    client = _client(monkeypatch, tmp_path, schema)

    assert client.delete_recipe("soup") is True
    assert _count(client, "recipes") == 1
    assert _count(client, "notes") == 0
    client.close()


def test_delete_recipe_rolls_back_on_failure(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, _SCHEMA_V328)
    # An unknown table referencing the recipe makes the final delete fail.
    client._db.execute("CREATE TABLE extra (recipe_id CHAR(32) REFERENCES recipes (id))")
    client._db.execute("INSERT INTO extra VALUES ('r1')")
    client._db.commit()

    with pytest.raises(sqlite3.IntegrityError):
        client.delete_recipe("soup")

    assert _count(client, "recipes") == 2
    assert _count(client, "notes") == 1
    assert _count(client, "recipe_ingredient_ref_link") == 2
    client.close()


def test_delete_recipe_returns_false_for_unknown_slug(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, _SCHEMA_V328)
    assert client.delete_recipe("missing") is False
    client.close()
