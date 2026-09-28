# Changelog

All notable changes to CookDex are documented here.

## [Unreleased]

A redesign around five places: Library, Organize, Discover, Automations and Settings. Changes to Mealie are shown or confirmed before they happen, Organize and the review sheet back up before they write, and Backup First is on by default for live runs.

### Added
- **Library home** — Replaces the Overview. A library score built from four fixable parts (categorized, tagged, ingredients linked, servings set) and a "Needs attention" list of findings, each with real examples and one action: review, merge, parse or fill in. Scan again runs only read-only checks, and fixes applied from the Library trigger a fresh scan so stale findings are never shown. (#86)
- **Organize** — Edits Mealie directly instead of a copy of the taxonomy. Tags, categories and tools show recipe counts, suggested merges and unused entries. Cookbooks show how many recipes match and their filter in words, with a filter builder, a live preview and "Missing tag" warnings. Food labels, foods and units get merges (the old name is kept as an alias so new recipes still parse), plurals, aliases and label assignment. Changes are staged, reviewed together and applied in one run with a backup first, and each is re-checked against Mealie before it's applied. (#87, #93)
- **Starter sets** — A new or sparse library is offered sets of meal types, cuisines, diets, main ingredients, occasions, kitchen tools and grocery aisles. Items the library already has, including plural and punctuation variants, are left out. (#93)
- **Taxonomy import and export** — Organize exports the whole taxonomy as one JSON file whose sections match `configs/taxonomy`, with cookbook filters written by name so they work on another server. Importing a bundle or single section files only adds and updates, and everything is staged for review first. Export warns about cookbook filters that point at deleted tags or categories, and importing names can repair them. (#93)
- **Review before you apply** — Clean Recipe Library previews open a review sheet: non-recipes and duplicates pre-selected, borderline entries for you to decide, new names editable. Only approved items that still qualify are changed, and the sheet reports what was done, kept or skipped. Previews also summarize their results in a sentence. (#85)
- **First-run setup** — New owners connect Mealie (tested before saving), scan the library and see the results in three steps. (#85)
- **Discover** — Replaces Recipe Sources. Sources are grouped by cuisine, show what each contributed, and can be previewed or imported from the page. "Check sources that are on" finds unreachable ones. (#88)
- **Automations** — Three routines, each a switch and a local time: nightly Mealie backup (keeps 7), a weekly read-only library check, and a weekly import of up to 10–100 new recipes. Routines that change Mealie need an owner's approval. Run history says whether a run was automatic or manual, a preview or applied, and why it failed or was skipped. (#90)
- **Structured run results** — Jobs record their results with the run (`GET /runs/{id}/result`), so result views survive log rotation. (#78)
- **Provider layer** — Groundwork for supporting recipe managers besides Mealie, starting with Tandoor. Organize runs through it, and tasks a backend can't run are marked unavailable. See `docs/PROVIDERS.md`. (#81)

### Changed
- **Automations are workflows** — An automation is now a list of steps, each a job with its own settings, plus settings for the whole run (preview or apply, back up first, stop when a step fails) and a trigger (only when you run it, every day, every week, every few hours, or once). Each automation says what it will do in one sentence, shows its steps as a chain, and has Preview now, Run now and an on/off switch. It runs as one job, with each step's progress and results shown in turn. Four ready-made automations ship switched off: nightly backup, weekly library check, weekly organizing of new recipes (preview), and weekly import. Schedules made before, including the old routines and any made in the classic view later, become automations with the same timing, options and approval. Approval to change Mealie on its own is given per automation, by an owner; an editor who changes what an approved automation does withdraws it.
- **Tools** — The Tasks page is replaced by Tools: jobs grouped by what you want to get done, in plain words, each with the one or two choices most people need and every other option under More options. Jobs preview first; applying is one step further and asks about a backup. Run automatically turns a job into an automation. The old page is still there as the classic view.
- **Readable run details** — Runs open in a details view that leads with a sentence ("20.6% of 12,169 recipes are complete. What's most often missing: cooking times.") and the numbers that matter, lists warnings and errors in plain words (grouped when the same thing happened many times), shows live progress while running, and offers Apply these changes after a preview. The raw log, options and exit code are under Technical details, with copy and download. Tools, Automations and the Library's recent activity all use it.
- **People** — Adding a person asks for a name and a role, makes a temporary password, and shows the sign-in details to send them, with Copy all. New password does the same for someone who's locked out. Roles are explained in plain words, each person shows when they last signed in, and you can change your own password.
- **Settings are set in CookDex, not the compose file** — Settings is grouped by what you're setting up (Mealie, AI helper, faster database access, recipe sources, updates and runs), each with a status, plain descriptions and one Save button that counts your changes. The compose file only needs container settings (port, base path, HTTPS, headless bootstrap), listed on the page. On first start, Mealie, AI and database values an older `.env` still sets are copied into Settings once (secrets encrypted), and the page says which lines can go. `.env.example` now lists only container settings.
- **One database connection string, used automatically** — The optional database connection is one `postgresql://…` or `sqlite://…` string instead of seven fields, with Test connection reporting the recipe count and Find it over SSH filling it in. The per-task **Use Direct DB** switches are gone: jobs use the database whenever it's saved and fall back to the API, with a note in the log, when it can't be reached. Older `MEALIE_DB_TYPE` / `MEALIE_PG_*` settings still work and are combined into the new one on first start.
- **Rule tagging without the database** — Ingredient and tool rules now also run through Mealie's API, so both paths tag the same way. They read each recipe's foods and steps once and remember them, so later runs only open recipes that changed. Changes are worked out first and each recipe is saved once with only what it gained, several at a time; a save Mealie rejects is retried once from a fresh copy. On a 12,169-recipe test library, tagging 10,053 recipes through the API went from about 17 minutes to 11 (with the database: 7 seconds), and a preview takes 4.5 seconds after the first run.
- **Slug repair without the database** — Repair Recipe Slugs fixes recipes through Mealie's API (Mealie makes a new slug when a name changes), or in one transaction when the database is connected. Recipes whose slug another recipe already has are skipped and listed, and previews say what would change instead of logging it as done.
- **Scan progress and speed** — While the Library scans, it shows each step and how far along it is (for example "Checking recipes for pages that aren't recipes · 4,000 of 12,169"). The check for pages that aren't recipes opens recipes 8 at a time, and remembers what it found. The next scan only opens recipes that changed since.
- **Navigation** — The sidebar shows Library, Organize, Discover, Automations and Settings. Users moved to Settings › People, About to Help › About, and Tasks is reached from "All activity" and "All tools". Old links redirect. The URL is now the only source of truth for the page, so the root always opens the Library and each page opens at the top. (#80, #95)
- **Live runs ask first** — Run Live shows what will happen and whether a backup is made, and Backup First is on by default for runs that write. An owner's confirmed manual run no longer unlocks the task's unattended-run policy; owners grant and revoke that explicitly. Installs that already ran a live task keep the policy on for it, with a Revoke note in the task panel. (#68)
- **Recipe sources are opt-in** — New installs start with every suggested source switched off, and each run imports at most 25 new recipes by default (`--max-total`). Existing installs keep their choices. (#88)
- **Settings and notices** — Settings fields follow the order people fill them in, env var names are behind a toggle, and the AI section offers "Off (rules only)". Notices are toasts colored by tone, and errors stay until dismissed. (#85)
- **Name cleanup** — Catches more SEO noise, such as "| The Best Recipe!", "(Seriously!)", shouted words, "recipe video" tails and copy numbers like `banana-bread-2`. Every rename is reviewed before it's applied. (#85)
- **One Mealie client** — Rule-based tagging, AI tagging and cookbook updates share the main client's authentication, retries and pagination. (#92)

### Fixed
- **Testing the database connection changed the server's environment** — Test connection set the database variables on the running server while it checked, so a task starting at the same moment could pick up an unsaved draft. The test now builds its own connection.
- **AI tagging suggested no categories** — The AI only ever saw recipe names, because the prompt read ingredients from a field Mealie doesn't send. It was also told to leave categories empty when unsure. On a real library, 20 uncategorized recipes got 0 categories. With the real ingredients, a short description and a clearer rule, they got 16. Tag & Categorize can also try the AI on a few recipes first ("Try on at Most"), and fill in only missing categories, tags or tools. The Library's "no category" finding uses the categories-only setting.
- **Ingredient links on the Library** — Without Direct DB, the quality audit counted every recipe as having unlinked ingredients, because Mealie's recipe list doesn't include ingredients. It now asks Mealie which recipes have linked ingredients. On a 12,169-recipe library, Ingredients linked went from 0% to the actual 82%.
- **Name cleanups that clash** — A suggested name that another recipe already has, or that two renames would share, is now flagged in the review and left unticked. If you apply one anyway, it gets a free slug (`plum-jam-2`) instead of colliding.
- **Which spelling a merge keeps** — When usage counts aren't available (for example with more than 1,500 foods), merge suggestions keep the clean, singular spelling: `salt` over `Salt +`, `anchovy` over `anchovies`.
- **Tool recipe counts** — Mealie reports `recipeCount: 0` for every tool, so Organize showed all tools as unused and offered "Delete all unused" for tools used by thousands of recipes. Tool counts now come from Mealie's recipe filter.
- **Backup pruning only touches CookDex's own backups** — The nightly routine and the Mealie Backup task's `keep` used to delete any Mealie backup beyond the newest N, sorted by file name, including backups made by hand, uploaded ones, and the restore points taken before each change. CookDex now records the backups it creates and prunes only those, by date. Restore points taken before a change are kept separately (newest 10). Backups that existed before this version are left alone. (#103)
- **Test Mealie** — A URL missing `/api` no longer "validates" against Mealie's web page, and `/api` is added automatically wherever the URL is used. Success names the Mealie version and user. (#69)
- **Stale screens** — Refresh, sign-in, setup and saving Settings load fresh data; the cache no longer renews its own lifetime. The five-minute auto-refresh no longer loads as a signed-out user and empties the People list. (#70, #94)
- **Tag & Categorize without AI** — A provider counts as ready only with credentials. Without one, the method defaults to Rules and the AI step is skipped with a message instead of a traceback. (#71)
- **Results find you** — The run you start is selected, and the finish notice says whether it was a preview or applied changes. (#74)
- **Restart recovery** — Runs left running or queued by a restart are closed out on startup. (#75)
- **Server stalls** — Slow calls such as a hung Mealie connection test no longer freeze every other request, including the health check Docker uses. (#77)
- **Schedules re-check approval** — Revoking a task's unattended-run approval now stops live schedules created earlier; a blocked run is recorded with the reason. A schedule whose task no longer exists is turned off with a reason instead of being skipped silently on every tick. (#89, #93)
- **Bad task options** — Invalid options return 422 with the reason instead of a 500. (#87)

### Removed
- **Taxonomy Editor, Refresh Taxonomy and Cookbook Sync** — Organize now edits tags, categories, tools, cookbooks, labels, foods and units directly in Mealie, with starter sets and JSON import/export, so CookDex no longer keeps its own copy of the taxonomy. On upgrade, whatever that copy held (and any unpublished editor draft) is saved to `reports/retired-managed-taxonomy-<time>.json`, which Organize can import. Schedules that used either task are turned off with a note saying why, and the `labels`, `tools`, `taxonomy` and `cookbooks` maintenance stages are skipped with a message. Rule-based tagging and the units cleanup now read Mealie's current tags, categories, tools and unit aliases. (#93)

## [2026.9.1] - 2026-09-26

### Added
- **Update notice** — Optional server-side release checks run on startup and cache results for 24 hours. A newer stable CalVer release appears in a banner dismissible per version and on About. Disable Check for Updates in Settings to prevent requests. Privacy text documents the request and its network metadata. (#64)

### Fixed
- **Retained taxonomy links** — Replace mode preserves IDs and recipe links for entries still in the source config. Missing entries are created before unwanted entries are deleted, and failed creation prevents destructive cleanup. (#53)
- **Conservative junk cleanup** — Suspicious titles no longer authorize deletion. Only records missing both meaningful ingredients and usable instructions qualify; ambiguous matches appear as review candidates in the report. Failed inspections now fail the job. (#52)
- **Direct DB group scope** — Jobs resolve the authenticated API user's group and verify it against the connected database, failing closed on mismatch. DB delete lookups also include that group. (#60)
- **Durable reimport resume** — A separate, atomically replaced completion checkpoint survives interrupted reports, repeated resumes, and previews. Completed recipes are filtered before the per-run limit. (#55)
- **Dedup keeper choice** — Copy suffixes, including numbered copies, are penalized like numeric duplicate suffixes so their longer titles do not win. (#57)
- **Dredger import limits** — Source duplicates and HTTP 409 responses are marked known without consuming the new-import budget. Running imports are drained when a site aborts so their results are recorded. (#58)
- **Read-only DB initialization** — Opening a Direct DB client no longer creates or commits schema indexes. (#61)
- **Build/version separation** — Ordinary web builds no longer increment the release version. The explicit version command synchronizes VERSION, package.json, and both root package-lock version fields. (#59)

### Changed
- **Shared job transport and failure handling** — Taxonomy sync and audit reuse shared pagination and retry sessions; food/unit merges use their explicit contracts. Taxonomy and cookbook write failures produce failing job status. Remaining PostgreSQL and broader job review work is split into #65 and #66. (#62)

## [2026.9.0] - 2026-09-26

### Added
- **Merge duplicate tags and categories** — `cleanup-duplicates` has new targets: Tags & Categories, Tags only, and Categories only. They merge near-duplicates through Mealie's native merge routes (Mealie v3.25+) instead of only reporting or deleting them. Names count as duplicates only when they differ by case, spacing, punctuation, accents, `&` vs `and`, or a plural ending whose singular also exists. Recipes move to the most-used spelling. Mealie doesn't update cookbook filters that point at the removed entry, so CookDex repoints those cookbooks too. Older Mealie servers are detected and skipped with a warning. (#45)
- **Rating and food-label cookbook filters** — Cookbook filters and the cookbook editor support `rating` comparisons (for example `rating >= 4`) and food labels (`recipeIngredient.food.label.name`, resolved to IDs at sync time). Out-of-range ratings are rejected, and a filter Mealie refuses now says which Mealie version it needs. (#46)

### Fixed
- **Ingredient parsing keeps per-line metadata** — Replacing unparsed ingredient lines no longer drops step-to-ingredient links, section titles, or recipe-specific substitutions (Mealie v3.26+). A title on a dropped header line moves to the next ingredient. A recipe whose linked or substituted line would be dropped goes to review instead of being patched. (#47)
- **Ingredient parsing no longer writes during dry runs** — New foods the parser proposes used to be created in Mealie as soon as a recipe was parsed, even in a dry run and even when the recipe was then sent to review. They are now created only right before a recipe is actually patched, and only once per run however many recipes share them. A dry run lists the foods it would create, and a recipe whose new food can't be created goes to review instead of being saved without it. (#51)
- **Reimport CLI required no `--apply`** — Running `python -m cookdex.recipe_reimporter` directly could write to Mealie without `--apply`. It now previews unless `--apply` is passed, and `DRY_RUN=true` still forces a preview. Web UI runs are unchanged. (#54)
- **Cleanup jobs reported success after failed writes** — Dedup, junk filter, name normalizer, reimport, yield normalizer, food/unit cleanup, label/tool sync, and tag/category merges now exit nonzero when their report records any failed operation, including partial failures. Data maintenance therefore stops at a failed cleanup stage unless `continue_on_error` is on. (#56)
- **Default cookbooks matched nothing** — The shipped `cookbooks.json` stored tag and category IDs from one specific Mealie instance, so every cookbook seeded from it came out empty everywhere else. It now uses names, which cookbook sync resolves against the connected Mealie. Existing installs still holding the old default filters are rewritten on startup; filters you have edited are left alone. **Initialize from Mealie** now stores organizer and label filters by name too. (#48)
- **Direct DB delete no longer edits other recipes** — Deleting a recipe through Direct DB used to remove the ingredient line from every recipe that used it as a sub-recipe. It now clears the link and keeps the line, filling an empty note with the deleted recipe's name. It also clears `users.owned_recipes_id`, which could block the delete on PostgreSQL. (#49)
- **Direct DB recipe delete on Mealie v3.26+** — The `clean-recipes` Direct DB fallback now clears ingredient substitutions (`recipes_ingredients_substitutions`), step-linked notes (`recipe_note_ref_link`), and step-linked ingredients (`recipe_ingredient_ref_link`) before their parent rows. Mealie declares these foreign keys without `ON DELETE CASCADE`, so on PostgreSQL a recipe using any of them could not be deleted. Tables missing from older Mealie versions are skipped, and a failed delete now rolls back completely and reports the error instead of silently continuing with a partial delete.

### Changed
- **Mealie v3.28.0 recertification** — Reviewed the v3.22.0–v3.28.0 releases, diffed the v3.21.0 and v3.28.0 OpenAPI specs and database schemas, and passed all 26 non-AI dry-run scenarios (including Direct DB) plus the 23 API scenarios in apply mode against the immutable v3.28.0 image. Ingredient substitutions and step-linked notes (new in v3.26) survive CookDex's recipe, food, and unit writes. None of the removed endpoints (`GET /auth/refresh`, `POST /groups/seeders/labels`, `POST /recipes/create/image`) were used by CookDex.
- **One compose file** — Removed `docker-compose.yml`, which duplicated `compose.ghcr.yml` with hardcoded port and refresh-mode values. `scripts/docker/update.sh` now uses `compose.ghcr.yml`, so `WEB_BIND_PORT` and `TAXONOMY_REFRESH_MODE` set in `.env` are honored there too.
- **Single dependency list** — Removed `requirements.txt`, which had drifted from `pyproject.toml` (it was missing `python-slugify`). The Dockerfile and Ubuntu installer now install from `pyproject.toml` only.
- **Repository housekeeping** — Removed agent planning notes under `docs/superpowers/`, renamed `AGENTS.MD` to `AGENTS.md`, and expanded `.dockerignore` so tests, docs, caches, and local runtime output stay out of the Docker build context.
- **`latest` now means the latest release** — Pushes to `main` publish `edge` and a `sha-` tag instead of moving `latest`, so `latest` changes only when a `v*` release is tagged. Use `COOKDEX_TAG=edge` to follow `main`.
- **Container image retention** — A weekly workflow deletes untagged images and all but the 20 newest `sha-` builds from GHCR. Releases, `latest`, and `edge` are never touched.
- **Web UI tests in CI** — Added `npm test` and a CI step to run `web/tests`, which existed but were never run.

## [2026.7.2] - 2026-07-26

### Security
- **PostCSS advisory** — Updated the transitive PostCSS dependency to 8.5.23, clearing a high-severity path-traversal advisory in the web build toolchain (arbitrary `.map` file disclosure through `sourceMappingURL` auto-loading).

### Fixed
- **About page card layout** — Project Links now sits directly below the CookDex details card in an independent desktop column instead of being pushed down by the taller Privacy & Data card.
- **Node version mismatch in the build toolchain** — Vite 8 requires Node `^20.19 || >=22.12`, but the documentation advertised Node 18, CI pinned the bare major `20` (which resolved to 20.18 and built with a version warning), and the Dockerfile build stage used `node:20-alpine`. The requirement is now declared once in `web/package.json` and CI, the Dockerfile, and the docs are checked against it by tests.
- **Live compatibility QA** — The Mealie dry-run pipeline now removes a retired `skip_ai` option and only injects `dry_run` into tasks that support it, restoring complete validation coverage instead of failing during task construction.

### Changed
- **Responsive layout coverage** — The About page now has a browser-level geometry regression test for the compact three-column desktop layout and the overflow-free single-column layout.
- **Mealie v3.21.0 recertification** — Pulled the immutable v3.21.0 image, reviewed the API surface and intervening releases, and passed all 25 non-AI CookDex compatibility scenarios.
- **Forked cross-promotion** — The About page and README now introduce [Forked](https://apps.apple.com/us/app/forked-recipes/id6760947117), Knownframe's native Mealie companion for recipe discovery, meal planning, and shopping lists.
- **Dark-mode screenshots** — Refreshed all five README product screenshots from the current CookDex interface at 1920×1080.
- **Contributor documentation** — `CONTRIBUTING.md` and `docs/LOCAL_DEV.md` now cover the ruff and bandit gate added in 2026.7.1; previously they described `pytest` alone, so a contributor could pass locally and fail CI.
- **Settings reference** — Documented `TAXONOMY_REFRESH_MODE`, `AI_BATCH_HEARTBEAT_SECONDS`, `OLLAMA_REQUEST_TIMEOUT`, and `OLLAMA_NUM_THREAD`, which appeared in no documentation, along with the 500-run history retention introduced in 2026.7.1.
- **README** — Added a requirements section and concrete before/after examples generated from the name normalizer rather than written by hand, and promoted recipe dredging from a bullet to a section describing what it actually verifies.
- **Security policy** — `SECURITY.md` no longer promises a response time.

## [2026.7.1] - 2026-07-25

### Security
- **Environment key injection through settings** — `PUT /settings` now rejects any key the environment catalog does not declare, and stored settings and secrets are filtered against the catalog before they are exported to task subprocesses. Previously the `settings` and `secrets` halves of the payload were unvalidated, so a saved key such as `PATH`, `PYTHONPATH`, or `LD_PRELOAD` was injected into the next task run's environment. Secret-backed keys sent through `settings` are also refused so they cannot be stored unencrypted.
- **Task option allowlists enforced server-side** — Option `choices` were previously sent to the UI for rendering but never checked on the server, leaving the API and saved schedules free to submit any value. They are now enforced when the execution is built, and the undocumented `config_file` passthrough that handed an arbitrary filesystem path to `rule_tagger --config` has been removed.
- **Login username enumeration** — A failed login now performs the same password-hash work whether or not the account exists, so response timing no longer distinguishes valid usernames.
- **Login rate limiting behind a proxy** — Attempts are tracked per username as well as per client IP, with a much larger IP allowance. Behind a reverse proxy every request shares the proxy's address, so a handful of failures previously locked out every user; a targeted lockout now follows the account being guessed while the IP bucket still caps credential stuffing. Idle buckets are swept instead of accumulating for the process lifetime.
- **SSH host key changes surfaced** — A changed host key during Mealie DB detection is no longer swallowed by a catch-all that silently retried over the `ssh` binary; it is reported to the caller as its own error.
- **Dredger site validation detail hardening** — Recipe source URL checks now return a generic validation failure instead of exposing hostname resolution results or the internal address rule that blocked the request.
- **Cache headers on API responses** — Authenticated JSON responses now carry `Cache-Control: private, no-cache` so they cannot be retained by a shared cache.

### Changed
- **Session cleanup moved off the request path** — Expired sessions were purged on every authenticated request, taking a global write lock and scanning the table each time. The sweep now runs on a periodic scheduler job; session lifetime is still enforced per request.
- **Run history retention** — Run rows are pruned to the most recent 500 by the same periodic job. Log files already rotated, so the table previously grew without bound and kept rows whose logs were long gone.
- **Database indexes** — Added indexes for session lookups by username and expiry and for the run history listing.
- **Settings API split** — SSH execution and Mealie DB credential detection moved out of `routers/settings_api.py` into `webui_server/db_detect.py`, roughly halving the router module.

### Fixed
- **Run history ordering** — Runs were ordered by `created_at` alone. That column comes from a wall clock whose resolution is coarse on some platforms, so runs created in quick succession can share a timestamp and the newest-N selection became arbitrary among them; with fully tied timestamps, pruning kept the oldest runs and deleted the newest. Ordering now breaks ties on `rowid`, which follows insertion order.
- **Corrupt password hashes** — `verify_password` now returns `False` for a malformed stored hash instead of raising on the base64 decode.
- **Invalid AI provider values** — The provider option now offers the values the categorizer actually accepts (`chatgpt`, `anthropic`, `ollama`). `openai` was previously accepted by the web UI and then rejected by the CLI mid-run.
- **Dead progress-throttle state in the ingredient parser** — Removed leftover timestamp bookkeeping from a time-based progress throttle that is now count-based.

### Performance
- **Logo assets** — The two branding images were 1536×1024 PNGs of about 2 MB each, together 91% of the web UI payload. Converted to WebP at the same resolution: 4084 KB → 130 KB (−97%), with a mean per-channel difference of 0.07/255 at the sizes they actually render. The PNG originals remain in `branding/`.
- **Response compression** — Added gzip for API and static responses. JavaScript and CSS previously transferred uncompressed at 419 KB; they now transfer at about 118 KB.
- **Immutable caching for build assets** — Vite emits content-hashed filenames, so `/assets/*` is now served with a one-year immutable `Cache-Control` and no longer costs a revalidation round-trip per file on repeat loads.
- **Database connection reuse** — `StateStore` opened a new SQLite connection and re-applied its PRAGMAs for every operation, which measured 0.253 ms against 0.0007 ms on a reused connection. One dashboard load made 41 connections; it now makes none beyond the first per thread, and the local request set dropped from 18.8 ms to 10.8 ms on an empty database.
- **Overview metrics** — The eight Mealie collections are now fetched concurrently instead of one after another, and the seven that are only needed as totals are counted through the pagination envelope's `total` rather than downloaded in full (servers that omit the field fall back to a full pass). Against a stub server at 150 ms latency the fetch went from 1273 ms to 167 ms.
- **Count queries for `/about/meta`** — Counts were computed by materializing rows: 500 full run records, every user, and every schedule — the last also probing the scheduler once per schedule. All are now `COUNT(*)`.
- **Config file listing** — The taxonomy collection probe ran one query per collection; it is now a single grouped query.
- **Dredger known-URL checks** — The scan loop queried the database once per candidate URL, opening a connection each time. Because a known URL skips the network entirely, re-scanning an already-crawled sitemap was purely database-bound. The known set is now loaded once per site: 286 ms → 0.6 ms per 1000 URLs.
- **Quality audit recipe query** — The five `LEFT JOIN`s produced a cartesian intermediate before aggregating (29,364 rows for 400 recipes). Each relation is now aggregated before it is joined back, for identical results about 9× faster.
- **Mealie connection pool** — The HTTP adapter used urllib3's default of 10 pooled connections while task pools and the metrics fetch can exceed that, forcing a fresh handshake per request. The pool is now sized explicitly.

### Added
- **Lint and security scanning in CI** — Ruff (scoped to defect-catching rules) and Bandit (baselined so it fails only on newly introduced findings) now run on every push and pull request.
- **Python 3.9 in the test matrix** — `requires-python` declares 3.9 as the floor but CI only exercised 3.11 and 3.12.

## [2026.6.1] - 2026-06-21

### Security
- **Web dependency security alerts** — Updated Vite to 7.3.5 and pinned the transitive esbuild dependency to 0.28.1, clearing the current npm audit findings for the web UI toolchain.

### Changed
- **Mealie v3.19.2 recertification** — Pulled the latest Mealie `mealie-next` branch through v3.19.2, reviewed the CookDex API compatibility surface, and updated the README compatibility badge to Mealie v3.19.2.

## [2026.5.3] - 2026-05-17

### Changed
- **Mealie v3.17 recertification** — Reviewed Mealie releases v3.15.0 through v3.17.0 and updated the README compatibility badge to Mealie v3.17.
- **Current Mealie API payloads** — Food creation now uses the current `POST /foods` schema before falling back to the legacy `groupId` payload, and food/unit merges use the documented v3 payloads directly.

## [2026.5.2] - 2026-05-02

### Changed
- **Library-backed parsing cleanup** — Replaced several hardcoded parsing and normalization paths with established library helpers across recipe URL handling, cookbook filters, recipe naming, re-imports, yield normalization, taxonomy workspace checks, and web utility formatting.

### Fixed
- **Parser edge-case coverage** — Added focused regression tests around categorizer JSON recovery, URL canonicalization, cookbook matching, settings detection, taxonomy workspace validation, recipe re-imports, and maintenance cleanup helpers.

## [2026.5.1] - 2026-05-02

### Fixed
- **Docker recipe source defaults** — Recipe Sources now loads packaged default sites from `COOKDEX_ROOT` before falling back to module-relative paths, restoring default site loading and `recipe-dredger` setup for Docker installs.

## [2026.4.2] - 2026-04-25

### Security
- **Dredger SSRF protection** — Sitemap URLs, recipe candidates, and redirect targets are now validated before crawler and verifier requests, blocking private, link-local, metadata, and non-HTTP targets.
- **Forced password reset enforcement** — Password changes revoke existing sessions for the target user, and accounts with pending forced resets are blocked from non-reset endpoints server-side.
- **Ollama validation detail hardening** — Settings connection tests now return a generic validation failure instead of exposing hostname resolution or validation exception details.

### Fixed
- **Dredger dry-run isolation** — Preview runs no longer persist imported, rejected, or retry state, preventing dry runs from causing later live imports to skip recipes.
- **Backup pruning safety** — Backup pruning now requires dangerous-task approval and validates retention with `keep >= 1`.
- **Release helper** — `scripts/release.sh` now works when run without optional bump arguments.
- **Web UI QA smoke** — The local smoke test keeps the backup retention default intact when exercising the task options flow.
- **Ollama settings test** — Invalid Ollama URLs now return a validation failure instead of raising from the settings API.
- **Ollama categorizer recovery** — JSON recovery handles Ollama-style responses more reliably.
- **Favicon safe area** — Browser, PWA, and app icons were regenerated with safer padding so the CookDex mark is no longer clipped.

### Changed
- **Local-first UI loading** — Tasks, activity, schedules, settings, config, users, quality, about, and health data now load before slower live Mealie overview metrics refresh in the background.
- **Dashboard and task activity polish** — The Overview page now uses the refreshed dashboard treatment, and task rows include clearer log access that scrolls directly to the selected run output.
- **Ollama categorizer progress visibility** — Long-running local model categorization now reports progress more clearly, with additional Ollama tuning settings for context, output size, and batch size.
- **Documentation refresh** — The README is now onboarding-focused, technical docs and in-app Help Center content were checked against current behavior, and static documentation accuracy tests were added.
- **Web dependency refresh** — PostCSS was updated through the Dependabot npm group.

## [2026.4.1] - 2026-04-07

### Security
- **Role-based access control** — Users now have `owner` or `editor` roles; owner-only routes (users, settings, debug) are enforced server-side with atomic last-owner protections
- **Session cookie TTL** — Login cookies now set `Max-Age`/`Expires` matching `WEB_SESSION_TTL_SECONDS` so sessions survive browser restarts

### Fixed
- **Schedule validation** — Invalid schedule inputs rejected with 422 before DB writes; legacy broken schedules surface `validation_error` instead of silently failing
- **Backup timeout** — Mealie backup POST timeout increased from 2min to 15min, pre-command timeout from 5min to 20min, to support large datasets

### Changed
- Mealie badge updated to v3.14

## [2026.3.63] - 2026-03-25

### Security
- **SSRF fix** — Starter pack import endpoint now validates URLs through `_validate_service_url`, blocking private IPs, cloud metadata endpoints, and non-HTTP schemes
- **Prompt injection hardening** — Recipe names, slugs, and ingredients are sanitized before AI prompt interpolation (strips control chars, role markers, and common injection phrases)
- **Identified User-Agent** — Dredger crawler now sends `CookDex/{version}` with repo link instead of anonymous `python-requests` default
- **Rate limit floor** — Hard minimum 1s crawl delay that cannot be bypassed by configuration

### Changed
- Default site list moved from hardcoded Python to `configs/default_sites.json` — cleaner data/code separation

## [2026.3.62] - 2026-03-24

### Fixed
- **Runaway task prevention** — AI categorizer now aborts immediately when provider is unavailable (rate-limit/quota exhausted) instead of retrying indefinitely for days
- Rate-limit retries reduced from 15 to 5 per API call; raises `ProviderUnavailableError` on exhaustion
- Consecutive batch failure circuit breaker — 3 failures in a row aborts the run
- **4-hour max run duration** enforced on all tasks (configurable via `MAX_RUN_DURATION_SECONDS` in Settings)

### Changed
- Default ingredient parser confidence threshold lowered from 80% to 70% — dramatically reduces expensive OpenAI parser fallbacks
- Categorizer batch size increased from 20 to 50 — fewer API calls, better cost amortization
- Categorizer prompts compacted to comma-separated taxonomy lists — reduces token usage per request

## [2026.3.61] - 2026-03-22

### Added
- **Privacy & Data** card on About page — shows telemetry, analytics, credential storage, and network access at a glance with detailed explanations
- **Privacy** section in README — documents data handling, credential storage, AI provider disclosure, and cookie usage
- **Bad scrape detection** in junk filter — catches recipes where the scraper produced garbled data:
  - Char-by-char HTML steps (scraper iterated an HTML string character by character, producing hundreds of single-char steps)
  - Collapsed ingredients (entire ingredient list jammed into a single note field as unparsed text)
- "Bad scrapes" option in junk filter reason dropdown (UI and CLI `--reason bad_scrape`)
- Mealie-to-Tandoor migration script (`scripts/migrate_mealie_to_tandoor.py`) — direct API-to-API recipe transfer with image support, resumability, and Unicode-safe output

## [2026.3.59] - 2026-03-22

### Added
- **Direct DB setup wizard** (`scripts/setup-db-tunnel.sh`) — interactive script that handles SSH key generation, copying, volume mounting, settings configuration, and container restart in one command
- Wizard writes SSH settings directly into CookDex's state database — no manual field entry needed
- "Merge Defaults" button on Recipe Sources — adds new curated sites from updates without removing existing sites
- Site add validation — checks reachability and requires a sitemap before adding; shows "Validating..." state during check

### Fixed
- SSH key validation now searches `/app/.ssh/` and `/tmp/.ssh-app/` in addition to `~/.ssh/`, and checks read permission — fixes "key not found" and permission errors in Docker
- SSH known_hosts path falls back to `/tmp/.ssh-app/` when `~/.ssh/` doesn't exist — fixes paramiko failure when `HOME=/nonexistent` (app user in Docker)
- Test DB now uses draft values from the UI like all other connection tests — no need to Apply Changes before testing
- Default SSH Key Path changed from `~/.ssh/cookdex_mealie` to `/app/.ssh/cookdex_mealie` to match the documented container mount path
- Tasks without a dry run option (e.g. Health Check) now show "Run" instead of misleading "Preview Run"

### Removed
- Removed 5 unreachable seed recipe sites (hard Cloudflare blocks / 406 rejections)

### Changed
- Renamed "Region" to "Group" throughout Recipe Sources — allows organizing sites by any category (e.g. Vegan, Budget, Keto), not just cuisine region; existing databases auto-migrate on startup
- Rewrote Direct DB docs — leads with setup wizard, then manual steps as fallback
- Removed misleading `pip install 'cookdex[db]'` from docs (dependencies are included in Docker image)
- Updated in-app help guides to match new wizard-first setup flow

## [2026.3.45] - 2026-03-21

### Added
- **Mealie Backup** task — create and prune Mealie backups via the admin API, with optional retention limit
- **Backup First** option on destructive tasks (Data Maintenance, Clean Recipes, Ingredient Parser, Tag & Categorize, Re-import, Cleanup Duplicates) — creates a Mealie backup before the task runs; hidden in dry-run mode
- Pre-command support in task runner — tasks can now run prerequisite commands (e.g. backup) before the main task, with automatic abort on failure
- Mealie server capabilities detection — connection test now probes `/about` for server version and feature flags
- `get_about()` method on `MealieApiClient` for querying Mealie server info
- Unit standardization fields (`standardUnit`, `standardQuantity`) supported in unit creation and alias metadata
- Mealie compatibility badge in README (validated against Mealie v3.13.1)
- Connection test response now includes `capabilities` object with `version` and `enableOpenaiTranscription`
- Health/debug report includes Mealie server capabilities alongside connection status

### Changed
- `_test_mealie_connection` returns server capabilities (version, transcription support) alongside connection status
- Settings test endpoint (`POST /settings/test/mealie`) returns `capabilities` when connection succeeds
## [2026.3.44] - 2026-03-21

### Security
- Subprocess env isolation — tasks receive only essential system vars + catalog vars, no longer inherit full parent env
- Added CSP, X-Frame-Options, X-Content-Type-Options, and Referrer-Policy security headers
- Debug endpoint no longer exposes internal Mealie/Ollama URLs — reports `set`/`not set` only
- Health endpoint no longer exposes app version or base path to unauthenticated callers
- SSH host validation tightened — removed `%` from allowed chars to prevent config injection
- SSH username and container name validation require alphanumeric first character to block flag injection
- SSRF protection extended to block Azure (168.63.129.16) and Alibaba Cloud (100.100.100.200) metadata IPs
- Auto-generated encryption key now stored in `.secrets/` subdirectory, separated from state database

### Accessibility (WCAG 2.1 AA)
- Added `:focus-visible` outlines on all interactive elements (buttons, inputs, nav items, toggles)
- Added `@media (prefers-reduced-motion: reduce)` to disable all animations
- Added `.sr-only` utility class for screen reader content
- Replaced `title` with `aria-label` on all icon-only buttons across Tasks, Users, Recipe Sources, and Recipe Organization pages
- Added `aria-label` to all search, filter, and unlabeled form inputs
- Added `scope="col"` to all table headers; empty header columns given sr-only labels
- Error/warning banners now use `role="alert"` and notice banners use `role="status"` for screen reader announcements
- Task badges (AI, DB) use `role="img"` with `aria-label` instead of title-only
- Improved disabled button contrast with explicit background/color instead of opacity-only

### Changed
- Replaced "Description" with "Ingredients Parsed" in gold medallion quality dimensions — all 6 dimensions are now actionable by the pipeline

## [2026.3.43] - 2026-03-21

### Changed
- Replaced "Description" with "Ingredients Parsed" in gold medallion quality dimensions — all 6 dimensions are now actionable by the pipeline

## [2026.3.42] - 2026-03-20

### Changed
- Split monolithic `App.jsx` (4925 lines) into 8 page components — App.jsx is now a 1160-line shell handling auth, routing, and shared state
- Extracted task log parser and renderers into `taskLogUtils.jsx`

### Docs
- Added missing `slug-repair` and `reimport-recipes` tasks to README, TASKS.md, and DIRECT_DB.md
- Fixed `tag-categorize` method default (`ai` → `both`) and added `recat` option in TASKS.md
- Fixed `ingredient-parse` confidence default (`75` → `80`) and added `max_recipes`/`no_cache` options in TASKS.md
- Added dredger-sites API endpoints to TASKS.md

## [2026.3.41] - 2026-03-20

### Added
- `--no-cache` flag for ingredient parser to bypass scan cache and reprocess all unparsed recipes
- "Bypass Cache" toggle in Tasks UI for ingredient parser
- Concurrent recipe prefetch (8 workers) for significantly faster parser runs

### Fixed
- Ingredient parser was sending `strategy` instead of `parser` to Mealie API — brute force and OpenAI fallbacks were never actually used
- Recipes fetched from list endpoint were missing ingredient data, causing all recipes to be skipped as "empty"

## [2026.3.40] - 2026-03-17

### Added
- UI screenshots in README (overview, tasks, recipe sources, taxonomy, settings)
- Credit to original Recipe Dredger author (D0rk4ce) in Recipe Sources UI

### Fixed
- Overview page cookbooks count showing 0 — added cookbook fetch to overview metrics API

## [2026.3] - 2026-03-15

### Added
- **Recipe Dredger** — discover and import recipes from curated sites via sitemap crawling, with language filtering and parallel workers
- **Mobile-friendly UI** — touch targets, responsive tables, adaptive polling, hamburger menu navigation
- **URL-based routing** — pages reflect in the browser URL (`/cookdex/tasks`, `/cookdex/settings`, etc.) with back/forward support
- **ETag caching** — backend returns `304 Not Modified` for unchanged API responses; frontend skips re-parsing
- **SQLite metrics cache** — dashboard overview loads from cache (~100ms) instead of live Mealie API calls (~60s), invalidated after task runs
- **Workspace draft reset** — "Initialize from Mealie" and "Import Starter Pack" now reconcile the workspace draft automatically
- **Junk detection** — filters failed scrapes, GUIDs, and empty-ingredient recipes before import
- **DB indexes** — automatic index creation on Mealie tags/tools/categories tables for faster lookups
- **Slug repair task** — detect and fix slug mismatches between API and database
- **Recipe reimporter** — re-scrape recipes from their original source URLs with parallel workers

### Changed
- AI provider settings (OpenAI, Anthropic, Ollama) are now hidden when their provider is not selected
- Run polling adapts to activity: 5s when tasks are active, 30s when idle (was fixed 3s)
- Log polling increased from 1.5s to 3s with proper cleanup of stale closures
- Settings/taxonomy saves no longer trigger a full data reload — only the changed data is refreshed
- Taxonomy content is lazy-loaded when navigating to pages that need it
- Ingredient parser reuses bulk-fetched recipe data instead of re-fetching each recipe individually
- Deduplicator deletes recipes in parallel (4 workers) instead of sequentially
- Hover effects wrapped in `@media (hover: hover)` to prevent sticky states on touch devices
- Overview stats grid uses 4 → 2 → 1 column progression across breakpoints
- Docker volumes simplified: `./configs` mount removed (taxonomy data lives in SQLite)

### Removed
- 920 lines of dead code from the old recipe organization editor
- Unused `configs/config.json` (no code referenced it)
- `configs.defaults` backup layer from Dockerfile
- Unused `PROVIDER` environment variable from docker-compose

### Fixed
- Log viewer maximized mode was pushed off-screen on mobile by sidebar offset
- Ingredient parser was re-fetching every recipe individually after already bulk-fetching all of them
- Taxonomy workspace showed phantom diffs after importing from Mealie or starter pack
- Dredger live mode had double `/api` prefix causing 404 on all Mealie calls

### Security
- SSRF protection hardened with DNS resolution and private IP blocking
- SSH subprocess args passed via temp config file instead of CLI to prevent injection
- CodeQL alerts resolved for command injection and path traversal

## [2026.2] - 2026-02-28

### Added
- Web UI with task runner, scheduler, and settings management
- Multi-user authentication with password complexity enforcement
- Encrypted secret storage (Fernet cipher with auto-generated key)
- Taxonomy workspace with draft/validate/publish workflow
- Quality audit with gold/silver/bronze scoring
- Data maintenance pipeline (14-stage sequential processing)
- Ingredient parser with NLP + AI fallback and confidence thresholds
- Tag categorizer with rule-based and AI-powered classification
- Direct database access for bulk operations (PostgreSQL + SQLite + SSH tunnel)
