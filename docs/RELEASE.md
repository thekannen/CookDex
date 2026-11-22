# Releasing

Maintainer checklist for a CookDex release. Versions are CalVer `YEAR.MONTH.BUILD`, where the month is the month the release ships.

## Checklist

1. Fix and feature PRs target `beta`. Put "Closes #N" in the release PR to `main`; PRs to `beta` don't close issues.
2. Feature freeze on `beta`.
3. **[R5 flagship review](#r5-flagship-code-and-security-review)**, then fix its findings.
4. UAT: `-beta.N` tags publish the GHCR `beta` image only. Test against a real Mealie, with live runs as well as dry runs.
5. Release PR `beta` → `main`: `python scripts/bump_version.py` (bumps `VERSION`, `web/package.json`, `web/package-lock.json`) and close the CHANGELOG section.
6. Tag `vX.Y.Z` (publishes GHCR `latest`), then `gh release create vX.Y.Z --title X.Y.Z --notes-file <that CHANGELOG section> --latest`. A tag alone doesn't publish the GitHub Release.
7. Reset `beta` to `main` and point the GHCR `beta` tag at the release (`docker buildx imagetools create -t ghcr.io/thekannen/cookdex:beta ghcr.io/thekannen/cookdex:vX.Y.Z`).
8. **[R6 repo cleanup](#r6-repo-cleanup)** before the next release's feature work.

## R5: Flagship code and security review

- **When:** after feature freeze, before UAT, so UAT covers the fixes. If it can only run after UAT, re-test what its fixes touch.
- **Model:** the most capable model with allowance left (Claude Fable today), otherwise the default. Record which one ran it in the release PR.
- **Scope:** `git diff <last release tag>..beta`. Four read-only passes, each in a fresh session given the whole brief up front:
  1. **Security:** auth and sessions (first-run setup code, password hashing, login rate limit, cookies, the `X-Requested-With` CSRF check), secrets (encrypted in `state.db` with `MO_WEBUI_MASTER_KEY`, never logged), outbound URLs through `url_security.validate_service_url`, parameterized SQL in `db_client.py`, and every path that takes untrusted input: API request bodies, imported taxonomy files, scraped recipe pages, AI provider replies, Mealie responses.
  2. **Data integrity:** what CookDex writes to Mealie and keeps itself. Check that dry run stays the default and writes nothing; a recipe is saved to `deleted-recipes/` and read back before it's deleted, and restore brings it back whole; `state.db` migrations only append and never edit a shipped one; a job's lane and `writes` cover what it changes, so parallel runs can't touch the same items; reruns and retries don't create duplicate tags, foods, units or recipes; and a stopped or failed run leaves Mealie consistent.
  3. **Correctness:** `/code-review high` on the largest new or rewritten files, plus the fixes from passes 1 and 2.
  4. **Tests:** tests that pass whatever the code does; missing tests for the release's risky changes, each with what it should assert; flaky tests (timing, test order, shared state, Windows paths).
- **Output:** each finding with file:line, how to trigger it, severity, and the smallest fix (for a test: delete, rewrite or add). A cheaper model makes the fixes; each fix gets `python -m pytest`, `python -m ruff check src tests`, `python -m bandit -r src -ll -b .bandit-baseline.json` and `cd web && npm run build`.
- **Closed when:** every finding is fixed or filed as an issue against the release. If what CookDex stores, sends or deletes changed, update the [privacy policy](https://knownframe.com/privacy/cookdex/) and [Privacy and safety](https://knownframe.com/cookdex/docs/privacy-and-safety/) pages in the same release. Security fixes follow [SECURITY.md](../SECURITY.md).

## R6: Repo cleanup

- **When:** after the release ships, before the next release's feature work. List what you'd remove and get the maintainer's approval first. When unsure, archive instead of deleting.
- **Docs:** move the shipped release's records, finished plans and specs, and completed test ledgers to `docs/archive/`, each with a one-line `Archived YYYY-MM-DD` banner. Cut stale status from AGENTS.md. Remove copies of what [knownframe.com/cookdex/docs](https://knownframe.com/cookdex/docs/) holds (only LOCAL_DEV, PROVIDERS, API and this file stay in `docs/`). Check that links resolve, and that the User Docs text in AGENTS.md and CONTRIBUTING.md still matches.
- **Agent memory:** consolidate it, and drop facts the release made stale.
- **Git:** delete merged local and remote branches (`release/*`, `fix/*`, `claude/*`); ask before touching `main` or `beta`. Drop stashes, remove finished worktrees under `.claude/worktrees/` and run `git worktree prune`, and review untracked files.
- **Local data:** `scripts/dev/clean_repo.ps1 -DryRun` lists the caches (`.pytest_cache`, `.pytest_tmp*`, `.ruff_cache`, `build/`, `dist/`, `web/dist`, `__pycache__`); also prune stray `state.db` copies, `reports/` and `logs/` from test runs. Keep anything needed to debug the shipped build: published GHCR tags and the release's CHANGELOG notes. Leave `.tmp/uat/` and the `cookdex-uat` container alone while another checkout uses them.
- **Tests and scripts:** remove one-off scripts nothing references (check `scripts/qa/`), skipped tests that aren't deliberate opt-in or live tests, and fixtures nothing uses. Find the slowest tests with `python -m pytest --durations=20`, speed them up (sleeps, oversized fixtures, repeated setup), and merge duplicates; a cheaper model does this. Record the suite's run time before and after.
- **Closed when:** what was removed and the space freed are recorded in the release's tracking issue.
