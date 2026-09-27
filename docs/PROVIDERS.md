# Recipe-manager providers

CookDex works with Mealie today. The code in `src/cookdex/providers/` is the
seam for supporting other self-hosted recipe managers, starting with
[Tandoor](https://github.com/TandoorRecipes/recipes).

## How it fits together

| Piece | Where | What it does |
|---|---|---|
| Contract | `providers/base.py` | `RecipeProvider` protocol, `Capability` flags, `Term`, `ProviderInfo`, `ProviderError` |
| Mealie adapter | `providers/mealie.py` | Implements the contract over `MealieApiClient` |
| Backend choice | `providers/__init__.py` | `get_provider(env)` reads `COOKDEX_BACKEND` (default `mealie`) |
| Web API | `GET /api/v1/provider` | Backend name, capabilities, term kinds and wording. Doesn't contact the backend |
| Frontend | `web/src/features/provider/useProvider.js` | `useProvider()` hook; pages check `has(capability)` and use `vocabulary` for labels |
| Task gating | `TASK_REQUIREMENTS` in `webui_server/tasks.py` | Tasks list what they need; unsupported tasks are marked unavailable and refused with 409 |
| Contract tests | `tests/test_provider_contract.py` | Runs the same checks against every adapter in `ADAPTERS` |

Pages built on the provider (Organize today) work unchanged with any adapter
that passes the contract. Most task modules still call Mealie directly; they
are gated by `TASK_REQUIREMENTS` until they're ported.

## Adding a backend

1. Write `providers/<name>.py` with a class that implements `RecipeProvider`.
   Report only the capabilities you implement, and keep backend details
   (ids, slugs, keyword trees) inside the adapter.
2. Register it in `BACKENDS` (connected) and `DESCRIBERS` (unconnected, for
   `/provider`) in `providers/__init__.py`.
3. Add a factory to `ADAPTERS` in `tests/test_provider_contract.py` that builds
   it over a fake transport seeded with `SEED`, and make the contract pass.
4. Add `<name>` to the `COOKDEX_BACKEND` description in `env_catalog.py`.
5. Port task modules one at a time by moving their backend calls behind the
   provider, then relax their `TASK_REQUIREMENTS`.

## Tandoor mapping (planned)

Tandoor exposes a REST API with token auth and OpenAPI 3. Everything is scoped
to a *space*.

| CookDex concept | Tandoor | Notes |
|---|---|---|
| Health | `/api/space/current/`, `/api/user/` | Report the active space as part of `ProviderInfo` |
| Tags and categories | Hierarchical `/api/keyword/` | One `keywords` term kind with `parent_id`. Map "categories" to children of a configurable root keyword, and advertise `term_hierarchy` |
| Tools | none | Don't advertise `tools` |
| Rename | `PATCH /api/keyword/{id}/` | |
| Merge | `PUT /api/keyword/{id}/merge/{target}/` (also food, unit) | Native, so `merge_terms`, `merge_foods` and `merge_units` |
| Bulk tagging | `/api/recipe/batch_update/` | Faster than Mealie's per-recipe PATCH |
| Import URL | `/api/recipe-from-source/` then `POST /api/recipe/` | Returns parsed JSON only; the adapter must save it |
| Ingredient parsing | `/api/ingredient-from-string/` | Rule-based, one line per call |
| Collections | `/api/recipe-book/` with a `/api/custom-filter/` | Translate cookbook rules to Tandoor's saved-search JSON |
| Food labels | `/api/supermarket-category/` (foods carry `supermarket_category`) | Shopping aisles, like Mealie labels. Use a native merge if the target version has one; otherwise reassign foods, as the Mealie adapter does |
| Backup | none in the API | Leave `backup` unset; a pg_dump-based job is a separate feature |
| Slugs | none (integer ids) | Leave `slugs` unset; tasks that need it stay unavailable until ported |

Tandoor already merges foods, units and keywords, and applies aliasing
automations to new imports. CookDex's value there is library-wide cleanup
(duplicate recipes, junk pages, names), AI tagging, the Library findings
inbox, and Discover.

Risks: some list/retrieve schemas declare fields as required that the API
doesn't always return, so parse loosely. Releases are frequent, so pin a
tested version range as the README does for Mealie.
