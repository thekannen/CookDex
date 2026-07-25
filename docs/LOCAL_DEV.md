# Local Dev Testing

Run the web UI locally without building a Docker image. This starts the Python backend (which serves the built frontend) directly on your machine.

## Prerequisites

- Python 3.9+ with the repo installed (`pip install -e .`)
- Node 20.19+ or 22.12+ (required by Vite 8; older versions fail to build)
- Optional: a `.env` file in the repo root (copy from `.env.example` if you want local overrides)

## 1. Install dependencies (one-time)

```bash
pip install -e ".[dev]"
cd web && npm install && cd ..
```

## 2. Build the frontend

```bash
cd web && npm run build && cd ..
```

The backend serves files from `web/dist/` automatically when the directory exists.

## 3. Optional local env vars

The UI can start without a `.env` file. It will show the setup screen and auto-generate a local encryption key.

For local testing with a pre-created admin account and placeholder Mealie connection, use:

```bash
# .env
MEALIE_URL=http://127.0.0.1:9000/api
MEALIE_API_KEY=placeholder
WEB_BOOTSTRAP_USER=admin
WEB_BOOTSTRAP_PASSWORD=DevPass-1
MO_WEBUI_MASTER_KEY=local-dev-testing-key
WEB_COOKIE_SECURE=false
```

`WEB_COOKIE_SECURE=false` is required for `http://localhost` (no HTTPS).

## 4. Start the server

```bash
python -m cookdex.webui_server.main
```

Open `http://localhost:4820/cookdex`.

## Quick restart loop

After making backend changes, Ctrl-C and re-run step 4. For frontend changes, rebuild first:

```bash
cd web && npm run build && cd .. && python -m cookdex.webui_server.main
```

## Vite dev server (frontend-only hot reload)

If you're only editing frontend code and want instant hot reloading, run Vite's dev server alongside the Python backend:

**Terminal 1** — backend:
```bash
python -m cookdex.webui_server.main
```

**Terminal 2** — Vite dev server with API proxy:
```bash
cd web && npm run dev
```

Then open the Vite URL (usually `http://localhost:5173`). If you need API calls to go through the Vite dev server, add a local proxy config to `web/vite.config.js`:

```js
// web/vite.config.js
import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  server: {
    proxy: {
      "/cookdex/api": "http://localhost:4820",
    },
  },
});
```

## Running tests

```bash
python -m pytest
```

Tests use their own in-memory fixtures and don't need `.env` or a running server.

## Running the CI checks locally

CI runs a lint and security gate alongside the tests, so run these before opening a
pull request — passing `pytest` alone is not enough:

```bash
python -m ruff check src tests
```

```bash
python -m bandit -r src -ll -b .bandit-baseline.json
```

Ruff is scoped to defect-catching rules (syntax errors, undefined names, bad
comparisons, dead imports and bindings) rather than style. Bandit runs against
`.bandit-baseline.json`, which records findings already reviewed as false
positives, so it fails only on newly introduced ones. If you add a finding that
is genuinely a false positive, explain it in the pull request rather than
regenerating the baseline.

## Automated QA loop

The QA script builds the frontend, starts the server, and runs Playwright smoke tests:

```bash
python scripts/qa/run_local_webui_qa.py --iterations 1
```

This requires Playwright browsers to be installed (`cd web && npx playwright install`).

## Troubleshooting

| Problem | Fix |
|---|---|
| Weak master key warning | Set a stronger `MO_WEBUI_MASTER_KEY` in `.env`, or let CookDex auto-generate one |
| 401 on login (cookie not sticking) | Set `WEB_COOKIE_SECURE=false` in `.env` |
| UI shows "build missing" | Run `cd web && npm run build` |
| Port already in use | Set `WEB_BIND_PORT=4821` in `.env` |
| Tasks page shows no tasks | Ensure the server started without errors; check terminal output |

## Workspace cleanup

Use the standard cleanup script when local artifacts start piling up:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev/clean_repo.ps1
```
