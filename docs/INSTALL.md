# Install

CookDex is deployed from GitHub Container Registry (`ghcr.io/thekannen/cookdex`).

## 1. Download the compose file

```bash
mkdir -p cookdex && cd cookdex
curl -fsSL https://raw.githubusercontent.com/thekannen/cookdex/main/compose.ghcr.yml -o compose.yaml
```

No `.env` file is required. To override defaults (port, base path, etc.), optionally download and edit `.env.example`:

```bash
curl -fsSL https://raw.githubusercontent.com/thekannen/cookdex/main/.env.example -o .env
```

## 2. Start the service

```bash
docker compose pull cookdex
docker compose up -d cookdex
```

## 3. Open the Web UI and complete setup

Open `https://localhost:4820/cookdex` in your browser. Accept the self-signed certificate warning on first visit.

1. Create your admin account (first-time setup screen).
2. Navigate to **Settings**.
3. Enter your **Mealie address** and **Mealie API token**.
4. Click **Test Mealie** to verify the connection.

## Required volumes

| Host path | Container path | Purpose |
|---|---|---|
| `./cache` | `/app/cache` | SQLite state database, encryption key, and TLS certificate |
| `./logs` | `/app/logs` | Task run log files |
| `./reports` | `/app/reports` | Audit and maintenance reports |

The `./cache` volume stores the state database (settings, run history, schedules), the auto-generated encryption key, and the TLS certificate. Keep this volume persistent.

## Updating

```bash
docker compose pull cookdex
docker compose up -d --remove-orphans cookdex
```

After updating, verify login and check `/cookdex/api/v1/health`.

### Image tags

| Tag | Tracks |
|---|---|
| `latest` | The most recent stable release (default). Betas never move it. |
| `beta` | The most recent beta, for trying the next release early |
| `v2026.x.y` | A specific release, never moved; betas are `v2026.x.y-beta.N` |
| `edge` | The newest build from `main`, which may include unreleased changes |
| `sha-<commit>` | A specific `main` build; only the 20 most recent are kept |

To use a different tag, set `COOKDEX_TAG` in `.env`.

## Notes

- All runtime settings are managed from the Settings page after login.
- Secrets (API tokens, the database connection string) are encrypted at rest. By default the key is generated on first start and kept in `./cache/webui/.secrets`, next to the database it protects, so anyone with a copy of `./cache` can decrypt them. To keep the key separate, set `MO_WEBUI_MASTER_KEY` (a Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) or `MO_WEBUI_MASTER_KEY_FILE` pointing at a file outside that volume, such as a Docker secret. Changing the key later makes saved secrets unreadable; Settings then asks for them again.
- Sign-in sessions are stored as SHA-256 hashes, so a copy of the database can't be used to sign in.
- Everything else (Mealie, AI, the optional database connection) is set in **Settings**. The optional `.env` file only holds container settings such as the port, base path and HTTPS. Older `.env` files that set Mealie or AI values still work; CookDex copies them into Settings on first start.
