# Database Connection

Every CookDex job works through Mealie's API. You don't need anything else.

On a large library, you can also give CookDex a connection to Mealie's database. The heavy jobs then read and write in bulk instead of one recipe at a time. Jobs use the connection on their own once it's saved, and fall back to the API (with a warning in the log) if it can't be reached. There's no per-task switch.

## What It Speeds Up

Measured on a test library of 12,169 recipes (Mealie v3.28 on PostgreSQL, same machine):

| Job | Through the API | With the database |
|---|---|---|
| Rule tagging, preview | 4.5 s (the very first run reads every recipe once: about 4 min) | 3.5 s |
| Rule tagging, saving 20,800 new tags on 10,053 recipes | about 11 min | 7 s |
| Health check | 9 s | 0.4 s |

Both paths find the same matches. Through the API, saving is limited by Mealie itself, which handled about 15 recipe saves a second here with a full CPU core busy. Smaller libraries, or jobs that change few recipes, won't notice much difference.

## Setup

1. Find Mealie's database settings in its compose file: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SERVER`, `POSTGRES_PORT` and `POSTGRES_DB`. Or on the Mealie host:

   ```bash
   docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' mealie
   ```

2. In CookDex, open **Settings -> Faster database access** and enter them as one connection string:

   ```
   postgresql://USER:PASSWORD@SERVER:PORT/DB
   ```

   If the password has characters like `@`, `/` or `:`, write them as `%40`, `%2F` and `%3A`.

3. Click **Test connection**. It reports how many recipes it found.
4. Save.

### Which host to use

Inside Docker, `localhost` is the CookDex container itself, not your server.

- CookDex and Mealie's Postgres on the same Docker network: use the Postgres container's name (Mealie's `POSTGRES_SERVER`, often `postgres`).
- Postgres published on the host: use the host's address and the published port.
- Postgres only reachable from the Mealie machine: use SSH (below).

### Over SSH

Open **Connect over SSH** in the same section when CookDex can't reach the database directly. CookDex signs in to the Mealie machine and connects to the database from there. The host and port in the connection string are then as seen from that machine (often `localhost:5432`).

| Setting | Example | Notes |
|---|---|---|
| SSH host | `192.168.1.100` | The Mealie machine. |
| SSH user | `your_ssh_user` | |
| SSH key file | `/app/.ssh/cookdex_mealie` | The path inside the CookDex container, not on the host. |

With an SSH host set, **Find it over SSH** reads Mealie's database settings from its container and fills in the connection string for you to review.

The setup script creates a key, installs it on the Mealie machine, mounts it into CookDex and saves the SSH settings:

```bash
docker cp cookdex:/app/scripts/setup-db-tunnel.sh /tmp/setup-db-tunnel.sh && bash /tmp/setup-db-tunnel.sh
```

Or by hand, on the machine running CookDex:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/cookdex_mealie -N ""
ssh-copy-id -i ~/.ssh/cookdex_mealie.pub your_ssh_user@192.168.1.100
```

then mount it in CookDex's compose file and recreate the container:

```yaml
services:
  cookdex:
    volumes:
      - ~/.ssh/cookdex_mealie:/app/.ssh/cookdex_mealie:ro
```

### SQLite

For a Mealie that uses SQLite, mount its database file into the CookDex container and use `sqlite:////path/inside/container/mealie.db` (four slashes for an absolute path).

## Older Setups

Earlier versions used separate settings (`MEALIE_DB_TYPE`, `MEALIE_PG_HOST`, `MEALIE_PG_PORT`, `MEALIE_PG_DB`, `MEALIE_PG_USER`, `MEALIE_PG_PASS`, `MEALIE_SQLITE_PATH`) and a **Use Direct DB** switch on each task. Both are gone from the UI. The old settings still work: on first start CookDex combines them into one connection string (`MEALIE_DB_URL`) in Settings. Tasks no longer need the switch; they use the connection whenever it's there.

## What CookDex Reads And Writes

CookDex uses parameterized SQL. Reads can include recipe rows, nutrition, ingredients and foods, instructions, category/tag/tool links, groups and users.

Writes are limited to the job being run:

- `yield-normalize`: recipe yield and servings fields
- `slug-repair`: recipe slug values
- `tag-categorize`: recipe-to-tag/category/tool links, and missing tags, categories or tools when **Missing Target Handling** is set to create
- `clean-recipes`: deleting a duplicate recipe the API can't delete, with its related rows, in one transaction
- `reimport-recipes`: repairing a slug when an older Mealie refuses an update

Use dry runs first when a task offers them.

## Scope

Database jobs still need the Mealie address and API token. They look up the API user's group and check it matches the database before selecting recipes, and stop if it doesn't. They never fall back to the first group in the database. **Test connection** checks connectivity only; a job checks scope when it runs.

Connecting doesn't create indexes or change Mealie's schema.

## What's Tested

`tests/test_db_integration.py` runs each database job against a fresh database built from Mealie v3.28's own schema (`tests/fixtures`), on both engines. SQLite always runs; PostgreSQL runs in CI, and locally when `COOKDEX_TEST_PG_URL` points at a server the tests may create databases on.

| Behavior | SQLite | PostgreSQL |
|---|---|---|
| Deleting a recipe removes its links, ingredients and instructions; the same slug in another group is untouched; a sub-recipe line keeps its text | ✓ | ✓ |
| A failed delete undoes every step, and the connection works for the next one | ✓ | ✓ |
| The deduplicator's database fallback, called from its worker threads, deletes every recipe (one transaction at a time) | ✓ | ✓ |
| One failed yield update doesn't lose the others; an update that matches no recipe counts as failed | ✓ | ✓ |
| Yield updates by API recipe id, and by slug within the group | ✓ | ✓ |
| Slug repair checks collisions within the recipe's group and accepts API ids | ✓ | ✓ |
| Reimport slug repair skips a slug another recipe has, and a failure doesn't stop the next repair | ✓ | ✓ |
| Tags match Mealie's slugs (`Crème Brûlée` finds `creme-brulee`); new ids and links use the engine's id format | ✓ | ✓ |
| Recipe rows are limited to the group; the API user's group is found from a dashed id | ✓ | ✓ |

Not covered: SSH tunnels, Mealie versions other than v3.28, and MySQL (which Mealie doesn't support).

## Local Source Installs

The Docker image includes the PostgreSQL and SSH drivers. For a source install:

```bash
pip install -e ".[db]"
```
