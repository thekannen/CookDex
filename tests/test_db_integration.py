"""Direct-database jobs against Mealie's real schema, on SQLite and PostgreSQL.

Every test runs on a fresh database built from Mealie v3.28's own schema
(tests/fixtures). SQLite always runs. PostgreSQL runs when
COOKDEX_TEST_PG_URL names a server the tests may create databases on, e.g.
postgresql://mealie:test@127.0.0.1:55432/mealie; CI starts one. Data is
synthetic.

The two engines store ids differently (PostgreSQL ``uuid``, SQLite 32 hex
characters), while the API hands out dashed UUIDs, so tests pass API-style ids
wherever the jobs receive them from the API.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

from cookdex.db_client import MealieDBClient, db_config

FIXTURES = Path(__file__).parent / "fixtures"
PG_URL = os.environ.get("COOKDEX_TEST_PG_URL", "").strip()

ENGINES = [
    "sqlite",
    pytest.param(
        "postgres",
        marks=pytest.mark.skipif(not PG_URL, reason="set COOKDEX_TEST_PG_URL to run against PostgreSQL"),
    ),
]


class MealieDB:
    """A throwaway Mealie database plus helpers to seed and inspect it."""

    def __init__(self, kind: str, url: str, raw) -> None:
        self.kind = kind
        self.url = url
        self.raw = raw  # a separate connection, for seeding and checking
        self.config = db_config({"MEALIE_DB_URL": url})

    def native(self, value) -> str:
        parsed = uuid.UUID(str(value))
        return parsed.hex if self.kind == "sqlite" else str(parsed)

    def sql(self, query: str, params: tuple = ()) -> list[tuple]:
        if self.kind == "sqlite":
            query = query.replace("%s", "?")
        cur = self.raw.cursor()
        cur.execute(query, params)
        rows = cur.fetchall() if cur.description else []
        self.raw.commit()
        return rows

    def client(self, group_id: str, monkeypatch) -> MealieDBClient:
        # get_group_id asks Mealie's API which group the token belongs to.
        monkeypatch.setattr(MealieDBClient, "get_group_id", lambda self: group_id)
        return MealieDBClient(self.config)

    # Seeding -------------------------------------------------------------

    def group(self, name: str) -> str:
        gid = uuid.uuid4()
        self.sql("INSERT INTO groups (id, name) VALUES (%s, %s)", (self.native(gid), name))
        return self.native(gid)

    def recipe(self, group_id: str, slug: str, name: str | None = None, **fields) -> str:
        """Add a recipe; returns its id as the API would give it (dashed)."""
        rid = uuid.uuid4()
        name = name or slug.replace("-", " ").title()
        cols = {"id": self.native(rid), "group_id": group_id, "slug": slug, "name": name,
                "name_normalized": name.lower(), **fields}
        marks = ", ".join(["%s"] * len(cols))
        self.sql(f"INSERT INTO recipes ({', '.join(cols)}) VALUES ({marks})", tuple(cols.values()))
        return str(rid)

    def tag(self, group_id: str, name: str, slug: str) -> str:
        tid = self.native(uuid.uuid4())
        self.sql("INSERT INTO tags (id, group_id, name, slug) VALUES (%s, %s, %s, %s)", (tid, group_id, name, slug))
        return tid

    def link_tag(self, recipe_id: str, tag_id: str) -> None:
        self.sql("INSERT INTO recipes_to_tags (recipe_id, tag_id) VALUES (%s, %s)", (self.native(recipe_id), tag_id))

    _ingredient_ids = iter(range(1, 10_000))

    def ingredient(self, recipe_id: str, note: str = "", referenced: str | None = None) -> int:
        iid = next(self._ingredient_ids)
        self.sql(
            "INSERT INTO recipes_ingredients (id, position, recipe_id, note, referenced_recipe_id) VALUES (%s, 0, %s, %s, %s)",
            (iid, self.native(recipe_id), note, self.native(referenced) if referenced else None),
        )
        return iid

    def instruction(self, recipe_id: str, text: str) -> None:
        self.sql(
            "INSERT INTO recipe_instructions (id, recipe_id, position, text) VALUES (%s, %s, 0, %s)",
            (self.native(uuid.uuid4()), self.native(recipe_id), text),
        )

    def fail_on(self, event: str, when: str) -> None:
        """Make every *event* (DELETE or UPDATE) on recipes matching *when* fail."""
        if self.kind == "sqlite":
            self.sql(f"CREATE TRIGGER cookdex_fail BEFORE {event} ON recipes WHEN {when} "
                     "BEGIN SELECT RAISE(ABORT, 'blocked by test'); END")
        else:
            self.sql("CREATE FUNCTION cookdex_fail() RETURNS trigger AS $$ "
                     "BEGIN RAISE EXCEPTION 'blocked by test'; END $$ LANGUAGE plpgsql")
            self.sql(f"CREATE TRIGGER cookdex_fail BEFORE {event} ON recipes FOR EACH ROW WHEN ({when}) "
                     "EXECUTE FUNCTION cookdex_fail()")

    def stop_failing(self) -> None:
        if self.kind == "sqlite":
            self.sql("DROP TRIGGER cookdex_fail")
        else:
            self.sql("DROP TRIGGER cookdex_fail ON recipes")

    # Reading ---------------------------------------------------------------

    def slugs(self, group_id: str) -> set[str]:
        return {row[0] for row in self.sql("SELECT slug FROM recipes WHERE group_id = %s", (group_id,))}

    def count(self, table: str, column: str, recipe_id: str) -> int:
        return self.sql(f"SELECT COUNT(*) FROM {table} WHERE {column} = %s", (self.native(recipe_id),))[0][0]


@pytest.fixture(params=ENGINES)
def mealie_db(request, tmp_path):
    if request.param == "sqlite":
        path = tmp_path / "mealie.db"
        raw = sqlite3.connect(path)
        raw.executescript((FIXTURES / "mealie_v3_28_sqlite_schema.sql").read_text(encoding="utf-8"))
        db = MealieDB("sqlite", f"sqlite:///{path}", raw)
        yield db
        raw.close()
        return

    import psycopg2

    name = f"cookdex_it_{uuid.uuid4().hex[:12]}"
    admin = psycopg2.connect(PG_URL)
    admin.autocommit = True
    admin.cursor().execute(f"CREATE DATABASE {name}")
    parts = urlsplit(PG_URL)
    url = urlunsplit(parts._replace(path=f"/{name}"))
    loader = psycopg2.connect(url)
    loader.autocommit = True
    loader.cursor().execute((FIXTURES / "mealie_v3_28_postgres_schema.sql").read_text(encoding="utf-8"))
    loader.close()
    raw = psycopg2.connect(url)
    try:
        yield MealieDB("postgres", url, raw)
    finally:
        raw.close()
        admin.cursor().execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        admin.close()


# Deleting recipes (deduplicator fallback) ---------------------------------------


def test_delete_removes_children_and_leaves_other_groups_alone(mealie_db, monkeypatch):
    home, other = mealie_db.group("Home"), mealie_db.group("Neighbours")
    soup = mealie_db.recipe(home, "soup")
    twin = mealie_db.recipe(other, "soup")
    stew = mealie_db.recipe(home, "stew")
    tag = mealie_db.tag(home, "Dinner", "dinner")
    mealie_db.link_tag(soup, tag)
    mealie_db.ingredient(soup, "2 carrots")
    mealie_db.instruction(soup, "Simmer.")
    sub_line = mealie_db.ingredient(stew, "", referenced=soup)

    with mealie_db.client(home, monkeypatch) as db:
        assert db.delete_recipe("soup") is True

    assert mealie_db.slugs(home) == {"stew"}
    assert mealie_db.slugs(other) == {"soup"}
    assert mealie_db.count("recipes_to_tags", "recipe_id", soup) == 0
    assert mealie_db.count("recipes_ingredients", "recipe_id", soup) == 0
    assert mealie_db.count("recipe_instructions", "recipe_id", soup) == 0
    assert mealie_db.count("recipes_ingredients", "recipe_id", twin) == 0  # untouched, had none
    # The stew keeps its line, readable, without the link to the deleted recipe.
    ref, note = mealie_db.sql("SELECT referenced_recipe_id, note FROM recipes_ingredients WHERE id = %s", (sub_line,))[0]
    assert ref is None and note == "Soup"


def test_failed_delete_rolls_back_every_step_and_the_connection_recovers(mealie_db, monkeypatch):
    home = mealie_db.group("Home")
    soup = mealie_db.recipe(home, "soup")
    mealie_db.recipe(home, "salad")
    tag = mealie_db.tag(home, "Dinner", "dinner")
    mealie_db.link_tag(soup, tag)
    mealie_db.ingredient(soup, "2 carrots")
    mealie_db.fail_on("DELETE", "OLD.slug = 'soup'")

    with mealie_db.client(home, monkeypatch) as db:
        with pytest.raises(Exception, match="blocked by test"):
            db.delete_recipe("soup")
        # Nothing of the recipe was removed...
        assert mealie_db.slugs(home) == {"soup", "salad"}
        assert mealie_db.count("recipes_to_tags", "recipe_id", soup) == 1
        assert mealie_db.count("recipes_ingredients", "recipe_id", soup) == 1
        # ...and the same connection still works for the next one.
        assert db.delete_recipe("salad") is True
    assert mealie_db.slugs(home) == {"soup"}


def test_deduplicator_database_fallback_from_worker_threads(mealie_db, monkeypatch):
    from cookdex import recipe_deduplicator
    from cookdex.recipe_deduplicator import RecipeDeduplicator

    home = mealie_db.group("Home")
    slugs = [f"dupe-{n}" for n in range(12)]
    for slug in slugs:
        rid = mealie_db.recipe(home, slug)
        mealie_db.ingredient(rid, "salt")
        mealie_db.instruction(rid, "Mix.")

    client = mealie_db.client(home, monkeypatch)
    monkeypatch.setattr(recipe_deduplicator, "resolve_db_client", lambda: client)
    dedup = RecipeDeduplicator(client=None, use_db=True, report_file=Path(os.devnull))
    with ThreadPoolExecutor(max_workers=4) as pool:  # as the deduplicator runs its deletes
        results = list(pool.map(dedup._try_db_delete, slugs))
    client.close()

    assert results == [True] * len(slugs)
    assert mealie_db.slugs(home) == set()


# Yields ---------------------------------------------------------------------------


def test_one_failed_yield_update_keeps_the_others(mealie_db, monkeypatch):
    home = mealie_db.group("Home")
    for slug in ("first", "bad", "last"):
        mealie_db.recipe(home, slug)
    mealie_db.fail_on("UPDATE", "OLD.slug = 'bad'")

    updates = [
        {"slug": "first", "recipe_yield": "4 servings", "recipe_servings": 4.0},
        {"slug": "bad", "recipe_yield": "2 servings"},
        {"slug": "last", "recipe_yield": "6 servings", "recipe_servings": 6.0},
        {"slug": "not-there", "recipe_yield": "1 serving"},
    ]
    with mealie_db.client(home, monkeypatch) as db:
        applied, failed = db.bulk_update_yield(updates, group_id=home)

    assert (applied, failed) == (2, 2)
    rows = dict(mealie_db.sql("SELECT slug, recipe_yield FROM recipes WHERE group_id = %s", (home,)))
    assert rows == {"first": "4 servings", "bad": None, "last": "6 servings"}


def test_yield_update_by_api_recipe_id_and_group_scope(mealie_db, monkeypatch):
    home, other = mealie_db.group("Home"), mealie_db.group("Neighbours")
    mine = mealie_db.recipe(home, "chili")
    mealie_db.recipe(other, "chili")
    with mealie_db.client(home, monkeypatch) as db:
        assert db.bulk_update_yield([{"recipe_id": mine, "recipe_servings": 8.0}]) == (1, 0)
        assert db.bulk_update_yield([{"slug": "chili", "recipe_yield": "8 bowls"}], group_id=home) == (1, 0)
    rows = mealie_db.sql("SELECT group_id, recipe_yield, recipe_servings FROM recipes WHERE slug = 'chili'")
    by_group = {mealie_db.native(gid): (yld, servings) for gid, yld, servings in rows}
    assert by_group[home] == ("8 bowls", 8.0)
    assert by_group[other] == (None, 0.0)


# Slugs ------------------------------------------------------------------------------


def test_slug_repair_checks_collisions_per_group_and_takes_api_ids(mealie_db, monkeypatch):
    from cookdex.slug_repair import apply_db_fixes

    home, other = mealie_db.group("Home"), mealie_db.group("Neighbours")
    mealie_db.recipe(other, "pasta")  # same slug in another group: no conflict
    pasta = mealie_db.recipe(home, "pasta-old", "Pasta")
    mealie_db.recipe(home, "pie")
    pie2 = mealie_db.recipe(home, "pie-old", "Pie")  # wants "pie", which is taken here
    monkeypatch.setenv("MEALIE_DB_URL", mealie_db.url)

    mismatches = [
        {"id": pasta, "db_slug": "pasta-old", "expected_slug": "pasta", "name": "Pasta"},
        {"id": pie2, "db_slug": "pie-old", "expected_slug": "pie", "name": "Pie"},
        {"id": str(uuid.uuid4()), "db_slug": "ghost", "expected_slug": "ghost-2", "name": "Ghost"},
    ]
    assert apply_db_fixes(mismatches) == (1, 1, 1)
    assert mealie_db.slugs(home) == {"pasta", "pie", "pie-old"}
    assert mealie_db.slugs(other) == {"pasta"}


def test_reimporter_slug_repair_skips_collisions_and_survives_failures(mealie_db, monkeypatch):
    from cookdex import recipe_reimporter
    from cookdex.recipe_reimporter import RecipeReimporter

    home = mealie_db.group("Home")
    mealie_db.recipe(home, "tacos")
    clash = mealie_db.recipe(home, "tacos-old", "Tacos")
    broken = mealie_db.recipe(home, "nachos-old", "Nachos")
    fine = mealie_db.recipe(home, "salsa-old", "Salsa")
    mealie_db.fail_on("UPDATE", "OLD.slug = 'nachos-old'")

    client = mealie_db.client(home, monkeypatch)
    monkeypatch.setattr(recipe_reimporter, "resolve_db_client", lambda: client)
    reimporter = RecipeReimporter(client=None, report_file=Path(os.devnull))

    assert reimporter._repair_slug("tacos-old", {"id": clash, "name": "Tacos"}) is None
    assert reimporter._repair_slug("nachos-old", {"id": broken, "name": "Nachos"}) is None
    # A failure before must not poison the connection (PostgreSQL aborts it).
    assert reimporter._repair_slug("salsa-old", {"id": fine, "name": "Salsa"}) == "salsa"
    client.close()
    assert mealie_db.slugs(home) == {"tacos", "tacos-old", "nachos-old", "salsa"}


# Tagging ------------------------------------------------------------------------------


def test_tags_match_mealie_slugs_and_links_use_native_ids(mealie_db, monkeypatch):
    home = mealie_db.group("Home")
    dessert = mealie_db.recipe(home, "creme-brulee", "Crème Brûlée")
    existing = mealie_db.tag(home, "Crème Brûlée", "creme-brulee")

    with mealie_db.client(home, monkeypatch) as db:
        # Found by Mealie's slug, not added again as "cr-me-br-l-e".
        assert db.ensure_tag("Crème Brûlée", home, dry_run=False) == existing
        weeknight = db.ensure_tag("Weeknight", home, dry_run=False)
        assert db.ensure_tag("weeknight", home, dry_run=False) == weeknight
        assert db.link_tag(dessert, weeknight, dry_run=False) is True
        assert db.link_tag(dessert, weeknight, dry_run=False) is False  # already linked
        db._db.commit()

    assert mealie_db.sql("SELECT COUNT(*) FROM tags")[0][0] == 2
    linked = mealie_db.sql(
        "SELECT r.slug FROM recipes r JOIN recipes_to_tags rt ON rt.recipe_id = r.id "
        "JOIN tags t ON t.id = rt.tag_id WHERE t.slug = 'weeknight'"
    )
    assert linked == [("creme-brulee",)]


def test_recipe_rows_and_group_lookup_by_api_ids(mealie_db, monkeypatch):
    home, other = mealie_db.group("Home"), mealie_db.group("Neighbours")
    soup = mealie_db.recipe(home, "soup")
    mealie_db.recipe(other, "stew")
    mealie_db.link_tag(soup, mealie_db.tag(home, "Dinner", "dinner"))
    user = uuid.uuid4()
    mealie_db.sql("INSERT INTO users (id, group_id) VALUES (%s, %s)", (mealie_db.native(user), home))

    with mealie_db.client(home, monkeypatch) as db:
        rows = db.get_recipe_rows(group_id=home)
        assert [(row["slug"], row["tag_count"]) for row in rows] == [("soup", 1)]
        assert mealie_db.native(db.get_group_id_for_api_key(str(user))) == home
