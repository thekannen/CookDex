"""Direct Mealie database client for high-throughput bulk operations.

Bypasses the HTTP API for operations that would otherwise require thousands of
individual PATCH/GET calls.  Uses raw parameterized SQL against the same
PostgreSQL (or SQLite) database that Mealie itself uses.

Supported operations
--------------------
  bulk_update_yield     – UPDATE recipe yield fields in a single transaction.
  get_recipe_rows       – SELECT all recipe rows with quality-scoring fields.
  get_group_id          – Resolve the authenticated API user's group UUID.

Configuration (environment variables)
--------------------------------------
  MEALIE_DB_URL           : one connection string, e.g.
                            postgresql://mealie:secret@postgres:5432/mealie
                            sqlite:////app/data/mealie.db
                            (unset → DB disabled)

  PostgreSQL via auto SSH tunnel (when PostgreSQL only listens on its own host):
    MEALIE_DB_SSH_HOST    : SSH host, e.g. 192.168.1.100
    MEALIE_DB_SSH_USER    : SSH user (default: root)
    MEALIE_DB_SSH_KEY     : path to private key (default: ~/.ssh/cookdex_mealie)
    The host and port in MEALIE_DB_URL are then as seen from the SSH host.

  Older setups may still use MEALIE_DB_TYPE with MEALIE_PG_HOST, _PORT, _DB,
  _USER and _PASS (or MEALIE_SQLITE_PATH); those keep working.
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Optional
from urllib.parse import quote, unquote, urlsplit


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _env(key: str, default: str = "", env: Optional[Mapping[str, str]] = None) -> str:
    source = os.environ if env is None else env
    return str(source.get(key, default) or default).strip()


@dataclass(frozen=True)
class DBConfig:
    """Where Mealie's database is and how to reach it."""

    kind: str  # "postgres" or "sqlite"
    host: str = "localhost"
    port: int = 5432
    database: str = "mealie_db"
    user: str = "mealie__user"
    password: str = ""
    sqlite_path: str = "/app/data/mealie.db"
    ssh_host: str = ""
    ssh_user: str = "root"
    ssh_key: str = ""

    def describe(self) -> str:
        """Where this points, without the password."""
        if self.kind == "sqlite":
            return f"SQLite file {self.sqlite_path}"
        where = f"{self.user}@{self.host}:{self.port}/{self.database}"
        return f"{where} through {self.ssh_user}@{self.ssh_host}" if self.ssh_host else where


def parse_db_url(url: str) -> dict[str, Any]:
    """Split a postgresql:// or sqlite:// connection string into DBConfig fields."""
    raw = url.strip()
    parts = urlsplit(raw)
    scheme = parts.scheme.lower().split("+", 1)[0]
    if scheme in {"postgres", "postgresql"}:
        if not parts.hostname:
            raise ValueError("The connection string needs a host, like postgresql://user:password@host:5432/mealie.")
        try:
            port = parts.port or 5432
        except ValueError as exc:
            raise ValueError("The port in the connection string isn't a number.") from exc
        database = unquote(parts.path.lstrip("/")) or "mealie"
        return {
            "kind": "postgres",
            "host": parts.hostname,
            "port": port,
            "database": database,
            "user": unquote(parts.username or "") or "mealie",
            "password": unquote(parts.password or ""),
        }
    if scheme == "sqlite":
        # sqlite:////abs/path.db → /abs/path.db ; sqlite:///rel.db → rel.db
        path = raw.split("://", 1)[1]
        path = path[1:] if path.startswith("/") else path
        if not path:
            raise ValueError("The connection string needs the path to mealie.db, like sqlite:////app/data/mealie.db.")
        return {"kind": "sqlite", "sqlite_path": unquote(path)}
    raise ValueError("Use a connection string that starts with postgresql:// or sqlite://.")


def build_db_url(fields: Mapping[str, Any]) -> str:
    """The connection string for DBConfig-style fields (the inverse of parse_db_url)."""
    if str(fields.get("kind", "")).startswith("sqlite"):
        return "sqlite:///" + str(fields.get("sqlite_path") or "/app/data/mealie.db")
    user = quote(str(fields.get("user") or "mealie"), safe="")
    password = str(fields.get("password") or "")
    auth = f"{user}:{quote(password, safe='')}" if password else user
    host = str(fields.get("host") or "localhost")
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = str(fields.get("port") or "5432")
    database = quote(str(fields.get("database") or "mealie"), safe="")
    return f"postgresql://{auth}@{host}:{port}/{database}"


def legacy_db_fields(env: Optional[Mapping[str, str]] = None) -> Optional[dict[str, Any]]:
    """DBConfig fields from the older MEALIE_DB_TYPE / MEALIE_PG_* settings, if set."""
    kind = _env("MEALIE_DB_TYPE", env=env).lower()
    if kind in {"postgres", "postgresql"}:
        return {
            "kind": "postgres",
            "host": _env("MEALIE_PG_HOST", "localhost", env),
            "port": int(_env("MEALIE_PG_PORT", "5432", env) or 5432),
            "database": _env("MEALIE_PG_DB", "mealie_db", env),
            "user": _env("MEALIE_PG_USER", "mealie__user", env),
            "password": _env("MEALIE_PG_PASS", env=env),
        }
    if kind == "sqlite":
        return {"kind": "sqlite", "sqlite_path": _env("MEALIE_SQLITE_PATH", "/app/data/mealie.db", env)}
    return None


def db_config(env: Optional[Mapping[str, str]] = None) -> Optional[DBConfig]:
    """The configured database, or None when Direct DB isn't set up.

    Raises ValueError when MEALIE_DB_URL is set but can't be read.
    """
    url = _env("MEALIE_DB_URL", env=env)
    fields = parse_db_url(url) if url else legacy_db_fields(env)
    if fields is None:
        return None
    return DBConfig(
        **fields,
        ssh_host=_env("MEALIE_DB_SSH_HOST", env=env),
        ssh_user=_env("MEALIE_DB_SSH_USER", "root", env) or "root",
        ssh_key=_env("MEALIE_DB_SSH_KEY", env=env),
    )


def db_type(env: Optional[Mapping[str, str]] = None) -> str:
    try:
        config = db_config(env)
    except ValueError:
        return ""
    return config.kind if config else ""


def is_db_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    return bool(db_type(env))


def wants_db(requested: bool) -> bool:
    """Use the database when asked to, or whenever it's connected."""
    return bool(requested) or is_db_enabled()


# ---------------------------------------------------------------------------
# DBWrapper — thin abstraction over psycopg2 / sqlite3
# ---------------------------------------------------------------------------

class DBWrapper:
    """Low-level connection wrapper for parameterised SQL execution.

    Supports PostgreSQL (%s placeholders) and SQLite (? placeholders) via a
    simple translation layer.  SQL can be written with %s and it will be
    converted for SQLite automatically.
    """

    def __init__(self, config: Optional[DBConfig] = None) -> None:
        config = config or db_config()
        if config is None:
            raise RuntimeError("Direct database access isn't set up. Add a connection string in Settings.")
        self.config = config
        self.conn: Any = None
        self.cursor: Any = None
        self._tunnel: Any = None  # sshtunnel.SSHTunnelForwarder, if opened
        self._type: str = config.kind
        self._ph: str = "%s" if self._type == "postgres" else "?"

        if self._type == "postgres":
            try:
                import psycopg2  # type: ignore[import]
            except ImportError as exc:
                raise RuntimeError(
                    "psycopg2 is required for PostgreSQL DB access.  "
                    "Install it with:  pip install 'cookdex[db]'  or  pip install psycopg2-binary"
                ) from exc

            pg_host, pg_port = self._resolve_pg_endpoint()
            try:
                self.conn = psycopg2.connect(
                    host=pg_host,
                    port=pg_port,
                    dbname=config.database,
                    user=config.user,
                    password=config.password,
                    connect_timeout=10,
                )
            except Exception:
                self.close()
                raise
            self.conn.autocommit = False
        else:
            import sqlite3  # stdlib
            if not os.path.isfile(config.sqlite_path):
                raise RuntimeError(f"No SQLite database at {config.sqlite_path}.")
            self.conn = sqlite3.connect(config.sqlite_path)
            self.conn.create_function("REGEXP", 2, self._sqlite_regexp)

        self.cursor = self.conn.cursor()

    def _resolve_pg_endpoint(self) -> tuple[str, int]:
        """Return (host, port) for PostgreSQL, opening an SSH tunnel if configured."""
        config = self.config
        ssh_host = config.ssh_host
        pg_host = config.host
        pg_port = int(config.port)

        if not ssh_host:
            return pg_host, pg_port

        try:
            from sshtunnel import SSHTunnelForwarder  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "sshtunnel is required for auto SSH tunnel.  "
                "Install it with:  pip install 'cookdex[db]'  or  pip install sshtunnel"
            ) from exc

        ssh_user = config.ssh_user or "root"
        ssh_key = config.ssh_key or "~/.ssh/cookdex_mealie"
        ssh_key = os.path.expanduser(ssh_key)
        if not os.path.isfile(ssh_key) or not os.access(ssh_key, os.R_OK):
            # Try documented Docker mount and entrypoint copy locations
            key_name = os.path.basename(ssh_key)
            for alt_dir in ["/app/.ssh", "/tmp/.ssh-app"]:
                alt = os.path.join(alt_dir, key_name)
                if os.path.isfile(alt) and os.access(alt, os.R_OK):
                    ssh_key = alt
                    break
        print(f"[db] Opening SSH tunnel -> {ssh_user}@{ssh_host} -> {pg_host}:{pg_port}", flush=True)
        print(f"[db] SSH key: {ssh_key} (exists={os.path.isfile(ssh_key)})", flush=True)

        tunnel = SSHTunnelForwarder(
            ssh_host,
            ssh_username=ssh_user,
            ssh_pkey=ssh_key,
            remote_bind_address=(pg_host, pg_port),
            allow_agent=False,
            host_pkey_directories=[],
            set_keepalive=10,
        )
        tunnel.start()
        self._tunnel = tunnel
        print(f"[db] Tunnel up on localhost:{tunnel.local_bind_port}", flush=True)
        return "127.0.0.1", tunnel.local_bind_port

    # ------------------------------------------------------------------
    # SQLite helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sqlite_regexp(expr: Optional[str], item: Optional[str]) -> bool:
        if not expr or item is None:
            return False
        try:
            # Translate PostgreSQL word-boundary markers (\y) to Python's \b
            py_expr = expr.replace(r"\y", r"\b")
            return bool(re.compile(py_expr, re.IGNORECASE).search(item))
        except re.error:
            return False

    def _translate_sql(self, sql: str) -> str:
        """Convert %s placeholders and PostgreSQL-isms to SQLite syntax."""
        if self._type != "sqlite":
            return sql
        sql = sql.replace("%s", "?")
        sql = re.sub(r"gen_random_uuid\(\)", "lower(hex(randomblob(16)))", sql)
        sql = sql.replace("::uuid", "")
        # Inline literal patterns:  col ~* 'pattern'
        sql = re.sub(r"([\w.]+)\s*~\*\s*'([^']+)'", r"\1 REGEXP '\2'", sql)
        sql = re.sub(r"([\w.]+)\s*!~\*\s*'([^']+)'", r"NOT (\1 REGEXP '\2')", sql)
        # Parameterized patterns:  col ~* ?  (after %s → ? conversion above)
        sql = re.sub(r"([\w.]+)\s*~\*\s*\?", r"\1 REGEXP ?", sql)
        sql = re.sub(r"([\w.]+)\s*!~\*\s*\?", r"NOT (\1 REGEXP ?)", sql)
        return sql

    # ------------------------------------------------------------------
    # Core execution interface
    # ------------------------------------------------------------------

    @property
    def placeholder(self) -> str:
        return self._ph

    def execute(self, sql: str, params: tuple = ()) -> "DBWrapper":
        self.cursor.execute(self._translate_sql(sql), params)
        return self

    def executemany(self, sql: str, params_seq: list[tuple]) -> "DBWrapper":
        self.cursor.executemany(self._translate_sql(sql), params_seq)
        return self

    def fetchone(self) -> Optional[tuple]:
        return self.cursor.fetchone()

    def fetchall(self) -> list[tuple]:
        return self.cursor.fetchall() or []

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def close(self) -> None:
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        try:
            if self._tunnel is not None:
                self._tunnel.stop()
                self._tunnel = None
        except Exception:
            pass

    def __enter__(self) -> "DBWrapper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


# ---------------------------------------------------------------------------
# MealieDBClient — high-level operations for cookdex tasks
# ---------------------------------------------------------------------------

class MealieDBClient:
    """High-level Mealie DB client.

    Instantiate and call the needed methods; close() when done.
    Prefer using as a context manager (``with`` block) for automatic cleanup.
    """

    def __init__(self, config: Optional[DBConfig] = None) -> None:
        self._db = DBWrapper(config)

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "MealieDBClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self._db.commit()
        else:
            self._db.rollback()
        self.close()

    # ------------------------------------------------------------------
    # Group helpers
    # ------------------------------------------------------------------

    def get_group_id(self) -> Optional[str]:
        """Resolve the configured API user's group; never guess from DB order."""
        from .api_client import MealieApiClient
        from .config import resolve_mealie_api_key, resolve_mealie_url

        client = MealieApiClient(resolve_mealie_url(), resolve_mealie_api_key(required=True))
        try:
            user = client.request_json("GET", "/users/self")
        finally:
            client.session.close()
        if not isinstance(user, dict) or not user.get("id"):
            raise RuntimeError("Cannot resolve authenticated Mealie user for Direct DB access.")
        group_id = self.get_group_id_for_api_key(str(user["id"]))
        if not group_id or str(user.get("groupId") or "").replace("-", "") != group_id.replace("-", ""):
            raise RuntimeError("Authenticated Mealie group does not match the connected database.")
        return group_id

    def get_group_id_for_api_key(self, api_user_id: str) -> Optional[str]:
        """Return group_id for the user associated with the API key."""
        row = self._db.execute(
            "SELECT group_id FROM users WHERE id = %s",
            (api_user_id.replace("-", "") if self._db._type == "sqlite" else api_user_id,),
        ).fetchone()
        return str(row[0]) if row else None

    # ------------------------------------------------------------------
    # Recipe quality reads
    # ------------------------------------------------------------------

    def get_recipe_rows(self, group_id: Optional[str] = None) -> list[dict]:
        """Return all recipes with fields needed for gold-medallion scoring.

        Includes tag, category, and tool counts via a single JOIN query —
        orders of magnitude faster than N individual API calls.
        """
        p = self._db.placeholder

        where = f"WHERE r.group_id = {p}" if group_id else ""
        params: tuple = (group_id,) if group_id else ()

        # Each related table is aggregated on its own before being joined
        # back, so the engine never materializes the cartesian product of
        # tags x categories x tools x ingredients per recipe. The previous
        # shape joined all four first and de-duplicated with COUNT(DISTINCT),
        # which is correct but grows multiplicatively with a large library.
        sql = f"""
            SELECT
                r.id,
                r.slug,
                r.name,
                r.description,
                r.recipe_yield,
                r.recipe_yield_quantity,
                r.recipe_servings,
                r.prep_time,
                r.total_time,
                r.perform_time,
                r.cook_time,
                COALESCE(tag.count_value, 0)  AS tag_count,
                COALESCE(cat.count_value, 0)  AS cat_count,
                COALESCE(tool.count_value, 0) AS tool_count,
                n.calories,
                COALESCE(ing.count_value, 0)  AS parsed_ingredient_count
            FROM recipes r
            LEFT JOIN (
                SELECT recipe_id, COUNT(DISTINCT tag_id) AS count_value
                FROM recipes_to_tags GROUP BY recipe_id
            ) tag  ON r.id = tag.recipe_id
            LEFT JOIN (
                SELECT recipe_id, COUNT(DISTINCT category_id) AS count_value
                FROM recipes_to_categories GROUP BY recipe_id
            ) cat  ON r.id = cat.recipe_id
            LEFT JOIN (
                SELECT recipe_id, COUNT(DISTINCT tool_id) AS count_value
                FROM recipes_to_tools GROUP BY recipe_id
            ) tool ON r.id = tool.recipe_id
            LEFT JOIN (
                SELECT recipe_id, COUNT(DISTINCT id) AS count_value
                FROM recipes_ingredients WHERE food_id IS NOT NULL GROUP BY recipe_id
            ) ing  ON r.id = ing.recipe_id
            LEFT JOIN recipe_nutrition n ON r.id = n.recipe_id
            {where}
        """
        rows = self._db.execute(sql, params).fetchall()
        keys = (
            "id", "slug", "name", "description",
            "recipeYield", "recipeYieldQuantity", "recipeServings",
            "prepTime", "totalTime", "performTime", "cookTime",
            "tag_count", "cat_count", "tool_count",
            "calories", "parsed_ingredient_count",
        )
        return [dict(zip(keys, row)) for row in rows]

    # ------------------------------------------------------------------
    # Yield bulk update
    # ------------------------------------------------------------------

    def bulk_update_yield(
        self,
        updates: list[dict],
        *,
        group_id: Optional[str] = None,
    ) -> tuple[int, int]:
        """Bulk-update recipe yield fields in a single transaction.

        Each ``update`` dict must contain:
            recipe_id       : str (UUID) — preferred
            OR slug + group_id : str

        And at least one of:
            recipe_yield            : str | None
            recipe_yield_quantity   : float | None
            recipe_servings         : float | None

        Returns (applied, failed).
        """
        applied = 0
        failed = 0
        p = self._db.placeholder

        for u in updates:
            try:
                sets: list[str] = []
                vals: list[Any] = []

                if "recipe_yield" in u:
                    sets.append(f"recipe_yield = {p}")
                    vals.append(u["recipe_yield"])
                if "recipe_yield_quantity" in u:
                    sets.append(f"recipe_yield_quantity = {p}")
                    vals.append(u["recipe_yield_quantity"])
                if "recipe_servings" in u:
                    sets.append(f"recipe_servings = {p}")
                    vals.append(u["recipe_servings"])

                if not sets:
                    continue

                if "recipe_id" in u:
                    vals.append(u["recipe_id"])
                    where = f"id = {p}"
                elif "slug" in u and (group_id or "group_id" in u):
                    gid = u.get("group_id") or group_id
                    vals.extend([u["slug"], gid])
                    where = f"slug = {p} AND group_id = {p}"
                else:
                    raise ValueError(f"update missing recipe_id or slug: {u!r}")

                sql = f"UPDATE recipes SET {', '.join(sets)} WHERE {where}"
                self._db.execute(sql, tuple(vals))
                applied += 1

            except Exception as exc:
                print(f"[db_error] yield update failed: {exc}", flush=True)
                failed += 1

        self._db.commit()
        return applied, failed

    # ------------------------------------------------------------------
    # Ensure tag / tool exist (used by future tagger tasks)
    # ------------------------------------------------------------------

    def _slug(self, name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    def lookup_tag_id(self, name: str, group_id: str) -> Optional[str]:
        """Return tag id for an exact name match (case-insensitive), else None."""
        p = self._db.placeholder
        row = self._db.execute(
            f"SELECT id FROM tags WHERE group_id = {p} AND lower(name) = lower({p}) LIMIT 1",
            (group_id, name),
        ).fetchone()
        return str(row[0]) if row else None

    def lookup_tool_id(self, name: str, group_id: str) -> Optional[str]:
        """Return tool id for an exact name match (case-insensitive), else None."""
        p = self._db.placeholder
        row = self._db.execute(
            f"SELECT id FROM tools WHERE group_id = {p} AND lower(name) = lower({p}) LIMIT 1",
            (group_id, name),
        ).fetchone()
        return str(row[0]) if row else None

    def lookup_category_id(self, name: str, group_id: str) -> Optional[str]:
        """Return category id for an exact name match (case-insensitive), else None."""
        p = self._db.placeholder
        row = self._db.execute(
            f"SELECT id FROM categories WHERE group_id = {p} AND lower(name) = lower({p}) LIMIT 1",
            (group_id, name),
        ).fetchone()
        return str(row[0]) if row else None

    def ensure_tag(self, name: str, group_id: str, *, dry_run: bool = True) -> Optional[str]:
        """Return tag id, creating it if necessary (unless dry_run)."""
        slug = self._slug(name)
        p = self._db.placeholder
        row = self._db.execute(
            f"SELECT id FROM tags WHERE slug = {p} AND group_id = {p}", (slug, group_id)
        ).fetchone()
        if row:
            return str(row[0])
        if dry_run:
            return "dry-run-id"
        new_id = str(uuid.uuid4())
        self._db.execute(
            f"INSERT INTO tags (id, group_id, name, slug) VALUES ({p}, {p}, {p}, {p})",
            (new_id, group_id, name, slug),
        )
        return new_id

    def ensure_tool(self, name: str, group_id: str, *, dry_run: bool = True) -> Optional[str]:
        """Return tool id, creating it if necessary (unless dry_run)."""
        slug = self._slug(name)
        p = self._db.placeholder
        row = self._db.execute(
            f"SELECT id FROM tools WHERE slug = {p} AND group_id = {p}", (slug, group_id)
        ).fetchone()
        if row:
            return str(row[0])
        if dry_run:
            return "dry-run-id"
        new_id = str(uuid.uuid4())
        self._db.execute(
            f"INSERT INTO tools (id, group_id, name, slug, on_hand) VALUES ({p}, {p}, {p}, {p}, FALSE)",
            (new_id, group_id, name, slug),
        )
        return new_id

    def link_tag(self, recipe_id: str, tag_id: str, *, dry_run: bool = True) -> None:
        """Associate a tag with a recipe (idempotent)."""
        if dry_run:
            return
        p = self._db.placeholder
        exists = self._db.execute(
            f"SELECT 1 FROM recipes_to_tags WHERE recipe_id = {p} AND tag_id = {p}",
            (recipe_id, tag_id),
        ).fetchone()
        if not exists:
            self._db.execute(
                f"INSERT INTO recipes_to_tags (recipe_id, tag_id) VALUES ({p}, {p})",
                (recipe_id, tag_id),
            )

    # ------------------------------------------------------------------
    # Rule-based tagger queries
    # ------------------------------------------------------------------

    def find_recipe_ids_by_ingredient(
        self,
        group_id: str,
        pattern: str,
        *,
        exclude_pattern: str = "",
        min_matches: int = 1,
    ) -> list[str]:
        """Return recipe IDs where parsed ingredient food names match *pattern*.

        Matching is case-insensitive regex (``~*`` on PostgreSQL; REGEXP on SQLite).
        Patterns may use ``\\y`` for word boundaries (PostgreSQL syntax); these are
        automatically translated to ``\\b`` for SQLite.

        If *exclude_pattern* is given, foods matching it are excluded from the
        matching set first.  *min_matches* sets the minimum number of distinct
        foods that must match before the recipe is included (use 2+ for cuisine
        fingerprinting).
        """
        p = self._db.placeholder
        where_parts = [f"r.group_id = {p}", f"f.name ~* {p}"]
        params: list = [group_id, pattern]
        if exclude_pattern:
            where_parts.append(f"NOT (f.name ~* {p})")
            params.append(exclude_pattern)
        where = " AND ".join(where_parts)
        params.append(min_matches)
        sql = f"""
            SELECT ri.recipe_id
            FROM recipes_ingredients ri
            JOIN recipes r ON r.id = ri.recipe_id
            JOIN ingredient_foods f ON ri.food_id = f.id
            WHERE {where}
            GROUP BY ri.recipe_id
            HAVING COUNT(DISTINCT f.id) >= {p}
        """
        return [str(row[0]) for row in self._db.execute(sql, tuple(params)).fetchall()]

    def find_recipe_ids_by_text(
        self,
        group_id: str,
        pattern: str,
        *,
        match_on: str = "both",
    ) -> list[str]:
        """Return recipe IDs where text fields match *pattern* (case-insensitive).

        ``match_on`` values:
          - ``both`` (default): name OR description
          - ``name``: name only
          - ``description``: description only
        """
        p = self._db.placeholder
        mode = str(match_on or "both").strip().casefold()
        if mode == "name":
            where_text = f"name ~* {p}"
            params: tuple[Any, ...] = (group_id, pattern)
        elif mode == "description":
            where_text = f"description ~* {p}"
            params = (group_id, pattern)
        else:
            where_text = f"(name ~* {p} OR description ~* {p})"
            params = (group_id, pattern, pattern)
        sql = f"""
            SELECT id
            FROM recipes
            WHERE group_id = {p}
              AND {where_text}
        """
        return [str(row[0]) for row in self._db.execute(sql, params).fetchall()]

    def find_recipe_ids_by_instruction(
        self,
        group_id: str,
        pattern: str,
    ) -> list[str]:
        """Return recipe IDs where any instruction step text matches *pattern* (case-insensitive)."""
        p = self._db.placeholder
        sql = f"""
            SELECT DISTINCT inst.recipe_id
            FROM recipe_instructions inst
            JOIN recipes r ON r.id = inst.recipe_id
            WHERE r.group_id = {p}
              AND inst.text ~* {p}
        """
        return [str(row[0]) for row in self._db.execute(sql, (group_id, pattern)).fetchall()]

    def link_tool(self, recipe_id: str, tool_id: str, *, dry_run: bool = True) -> None:
        """Associate a tool with a recipe (idempotent)."""
        if dry_run:
            return
        p = self._db.placeholder
        exists = self._db.execute(
            f"SELECT 1 FROM recipes_to_tools WHERE recipe_id = {p} AND tool_id = {p}",
            (recipe_id, tool_id),
        ).fetchone()
        if not exists:
            self._db.execute(
                f"INSERT INTO recipes_to_tools (recipe_id, tool_id) VALUES ({p}, {p})",
                (recipe_id, tool_id),
            )

    def ensure_category(self, name: str, group_id: str, *, dry_run: bool = True) -> Optional[str]:
        """Return category id, creating it if necessary (unless dry_run)."""
        slug = self._slug(name)
        p = self._db.placeholder
        row = self._db.execute(
            f"SELECT id FROM categories WHERE slug = {p} AND group_id = {p}", (slug, group_id)
        ).fetchone()
        if row:
            return str(row[0])
        if dry_run:
            return "dry-run-id"
        new_id = str(uuid.uuid4())
        self._db.execute(
            f"INSERT INTO categories (id, group_id, name, slug) VALUES ({p}, {p}, {p}, {p})",
            (new_id, group_id, name, slug),
        )
        return new_id

    def link_category(self, recipe_id: str, category_id: str, *, dry_run: bool = True) -> None:
        """Associate a category with a recipe (idempotent)."""
        if dry_run:
            return
        p = self._db.placeholder
        exists = self._db.execute(
            f"SELECT 1 FROM recipes_to_categories WHERE recipe_id = {p} AND category_id = {p}",
            (recipe_id, category_id),
        ).fetchone()
        if not exists:
            self._db.execute(
                f"INSERT INTO recipes_to_categories (recipe_id, category_id) VALUES ({p}, {p})",
                (recipe_id, category_id),
            )


    # ------------------------------------------------------------------
    # Recipe deletion (cascade)
    # ------------------------------------------------------------------

    # Rows that reference a recipe's own ingredients or instructions, keyed by
    # (table, column, parent table).  They must go before their parents because
    # Mealie declares these foreign keys without ON DELETE CASCADE.  The
    # substitution and note-link tables were added in Mealie v3.26.
    _GRANDCHILD_TABLES: list[tuple[str, str, str]] = [
        ("recipe_ingredient_ref_link", "instruction_id", "recipe_instructions"),
        ("recipe_note_ref_link", "instruction_id", "recipe_instructions"),
        ("recipes_ingredients_substitutions", "ingredient_id", "recipes_ingredients"),
    ]

    _FK_TABLES: list[tuple[str, str]] = [
        ("api_extras", "recipee_id"),
        ("group_meal_plans", "recipe_id"),
        ("notes", "recipe_id"),
        ("recipe_assets", "recipe_id"),
        ("recipe_instructions", "recipe_id"),
        ("recipe_nutrition", "recipe_id"),
        ("recipe_settings", "recipe_id"),
        ("recipe_share_tokens", "recipe_id"),
        ("recipes_to_categories", "recipe_id"),
        ("recipes_to_tags", "recipe_id"),
        ("recipes_to_tools", "recipe_id"),
        ("shopping_list_recipe_reference", "recipe_id"),
        ("recipe_comments", "recipe_id"),
        ("recipes_ingredients", "recipe_id"),
        ("shopping_list_item_recipe_reference", "recipe_id"),
        ("recipe_timeline_events", "recipe_id"),
        ("users_to_recipes", "recipe_id"),
        ("households_to_recipes", "recipe_id"),
    ]

    # Columns in rows that belong to someone else and merely point at the
    # recipe.  They are nulled rather than deleted: another recipe that uses
    # this one as a sub-recipe keeps its ingredient line.
    _NULLABLE_REFS: list[tuple[str, str]] = [
        ("recipes_ingredients", "referenced_recipe_id"),
        ("users", "owned_recipes_id"),
    ]

    def _existing_tables(self) -> set[str]:
        if self._db._type == "sqlite":
            rows = self._db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        else:
            rows = self._db.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
            ).fetchall()
        return {str(row[0]) for row in rows}

    def delete_recipe(self, slug: str) -> bool:
        """Delete a recipe and all FK references by slug. Returns True if deleted.

        Tables absent from the connected Mealie version are skipped.  Any other
        failure rolls the whole delete back and is raised, so a recipe is never
        left half-deleted.
        """
        p = self._db.placeholder
        group_id = self.get_group_id()
        row = self._db.execute(f"SELECT id FROM recipes WHERE slug = {p} AND group_id = {p}", (slug, group_id)).fetchone()
        if not row:
            return False
        rid = str(row[0])
        tables = self._existing_tables()
        try:
            if "recipes_ingredients" in tables:
                # Keep the sub-recipe line readable once the link is gone.
                self._db.execute(
                    f"UPDATE recipes_ingredients SET note = "
                    f"(SELECT name FROM recipes WHERE id = {p}) "
                    f"WHERE referenced_recipe_id = {p} AND (note IS NULL OR note = '')",
                    (rid, rid),
                )
            for table, col in self._NULLABLE_REFS:
                if table in tables:
                    self._db.execute(f"UPDATE {table} SET {col} = NULL WHERE {col} = {p}", (rid,))
            for table, col, parent in self._GRANDCHILD_TABLES:
                if table in tables and parent in tables:
                    self._db.execute(
                        f"DELETE FROM {table} WHERE {col} IN "
                        f"(SELECT id FROM {parent} WHERE recipe_id = {p})",
                        (rid,),
                    )
            for table, col in self._FK_TABLES:
                if table in tables:
                    self._db.execute(f"DELETE FROM {table} WHERE {col} = {p}", (rid,))
            self._db.execute(f"DELETE FROM recipes WHERE id = {p}", (rid,))
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return True


# ---------------------------------------------------------------------------
# Factory / connectivity check
# ---------------------------------------------------------------------------

def resolve_db_client() -> Optional[MealieDBClient]:
    """Return a connected MealieDBClient or None if DB is not configured."""
    if not is_db_enabled():
        return None
    try:
        return MealieDBClient()
    except Exception as exc:
        print(f"[db] Connection failed: {exc}", flush=True)
        return None
