## Issue Tracking

This project uses **GitHub Issues** (`thekannen/CookDex`) via the `gh` CLI.

**Quick reference:**
- `gh issue list` - Find open work
- `gh issue create --title "Title" --body "..." --label bug` - Create issue
- `gh issue close <number> --comment "..."` - Complete work
- `gh issue view <number>` - Read details

## User Docs

User docs live at [knownframe.com/cookdex/docs](https://knownframe.com/cookdex/docs/), which the maintainer updates. If a change alters what users see or do, say in the pull request which docs page needs a matching update. The files in `docs/` other than LOCAL_DEV, PROVIDERS and API are pointers to that site; don't add user docs back here. The app's Help page and job sheets link to those pages instead of carrying their own copy, so new help text goes on the site, not into `web/src/constants.js`.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
