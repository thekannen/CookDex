# Web UI API routes

These are the routes the CookDex web UI uses. They are not a stable public API yet.

All API routes are prefixed with `/cookdex/api/v1` by default. If `WEB_BASE_PATH` changes, replace `/cookdex` with your configured base path.

## API Routes

**Auth**

- `GET /auth/bootstrap-status`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/session`

**Tasks, Runs, Policies**

- `GET /tasks`
- `POST /runs`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/log`
- `GET /runs/{run_id}/log/tail`
- `GET /runs/{run_id}/result`
- `POST /runs/{run_id}/cancel`
- `GET /policies`
- `PUT /policies`

**Automations**

- `GET /automations`
- `POST /automations`
- `PUT /automations/{automation_id}`
- `POST /automations/{automation_id}/enabled`
- `POST /automations/{automation_id}/run`
- `DELETE /automations/{automation_id}`

**Schedules**

- `GET /schedules`
- `POST /schedules`
- `PATCH /schedules/{schedule_id}`
- `DELETE /schedules/{schedule_id}`

**Settings**

- `GET /settings`
- `PUT /settings`
- `POST /settings/models/openai`
- `POST /settings/models/anthropic`
- `POST /settings/models/ollama`
- `POST /settings/test/mealie`
- `POST /settings/test/openai`
- `POST /settings/test/anthropic`
- `POST /settings/test/ollama`
- `POST /settings/test/db`
- `POST /settings/detect/db`
- `GET /settings/dredger-sites`
- `POST /settings/dredger-sites`
- `PUT /settings/dredger-sites/{site_id}`
- `DELETE /settings/dredger-sites/{site_id}`
- `POST /settings/dredger-sites/seed`
- `POST /settings/dredger-sites/validate`

**Users**

- `GET /users`
- `POST /users`
- `POST /users/{username}/reset-password`
- `PATCH /users/{username}/role`
- `DELETE /users/{username}`

**Organize**

- `GET /provider`
- `GET /provider/status`
- `GET /organize/{kind}` (tags, categories, tools)
- `GET /organize/cookbooks`
- `POST /organize/cookbooks/preview`
- `GET /organize/labels`
- `GET /organize/foods`
- `GET /organize/units`
- `GET /organize/last-backup` (when CookDex last made a Mealie backup, read from its own records)
- `GET /organize/starter-packs`
- `GET /organize/export`
- `POST /organize/import`
- `POST /organize/standard/{kind}` (foods, units; only while the list is empty)

Organize reads live from the recipe manager. Changes are staged in the browser and applied with the hidden `organize-apply` task, so they get run history and the usual safety checks. A backup first is the default for changes that can lose data, and the apply sheet lets you skip it. Without a backup, the task runs in the light lane, beside a long job, unless its writes overlap that job's (see `webui_server/lanes.py`).

**Library and Discover**

- `GET /library`
- `POST /library/scan`
- `GET /discover`
- `POST /discover/sources/enabled`

**Meta**

- `GET /health`
- `GET /metrics/overview`
- `GET /metrics/quality`
- `GET /about/meta`
- `GET /debug-log`
