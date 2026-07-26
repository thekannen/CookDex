# About Layout Hotfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the About page's three-column blank-space regression and fold the correction into v2026.7.2.

**Architecture:** Render the real About component and stylesheet in Chromium to test card geometry. Replace the single four-card grid with three desktop columns, using a nested left column for the CookDex and Project Links cards, while preserving the existing one-column breakpoint.

**Tech Stack:** React 18, CSS Grid, Node test runner, Vite SSR, Playwright Chromium, Python/pytest, Ruff, Bandit.

## Global Constraints

- Desktop order is CookDex plus Project Links in the left column, Privacy & Data in the middle, and Also from Knownframe on the right.
- The left-column cards use the existing `0.9rem` page-grid gap.
- At `1180px` and below, the layout collapses to one column.
- Do not change About-page copy, links, colors, card styling, or backend behavior.
- Do not capture, commit, or update screenshots.
- Keep the release version at `v2026.7.2` and move that tag to the corrected protected-branch merge commit.

---

### Task 1: Protect the About card geometry

**Files:**
- Modify: `web/tests/AboutPage.test.mjs`

**Interfaces:**
- Consumes: Server-rendered `AboutPage` markup, `web/src/styles.css`, and the installed Playwright Chromium runtime.
- Produces: A browser-level regression test for the desktop card gap and narrow single-column layout.

- [x] **Step 1: Add the failing browser layout test**

Read the real stylesheet, render the real About component, and load both into
Chromium. Use an `1100px`-wide test container inside a `1440px` desktop
viewport. Locate cards by their headings and assert that Project Links begins
no more than `20px` below the CookDex card while the three desktop columns share
the same top coordinate. Resize to `760px`, remove the fixed container width,
and assert the cards share one left coordinate and do not overflow the
viewport.

- [x] **Step 2: Run the focused test and verify the expected failure**

Run:

```bash
node --test web/tests/AboutPage.test.mjs
```

Expected: the desktop assertion fails because Project Links starts after the
tall first grid row instead of immediately below the CookDex card.

### Task 2: Implement the independent-column layout

**Files:**
- Modify: `web/src/pages/about/AboutPage.jsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes: Existing `page-grid`, `card`, and `about-grid` styles.
- Produces: An `about-column` wrapper for the two left-column cards and an
  explicit three-column desktop grid.

- [x] **Step 1: Add the minimal layout structure**

Wrap the CookDex metadata and Project Links articles in:

```jsx
<div className="about-column">
  {/* CookDex metadata card */}
  {/* Project Links card */}
</div>
```

Keep Privacy & Data and Also from Knownframe as the second and third direct
children of `about-grid`.

- [x] **Step 2: Add the minimal CSS**

Replace the auto-fitting About grid with:

```css
.about-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: start;
}

.about-column {
  display: grid;
  gap: 0.9rem;
  align-content: start;
}
```

The existing `@media (max-width: 1180px)` rule continues to set
`.about-grid` to one column.

- [x] **Step 3: Run the focused test and verify it passes**

Run:

```bash
node --test web/tests/AboutPage.test.mjs
```

Expected: both rendered-content and browser-layout tests pass.

### Task 3: Validate and release the hotfix

**Files:**
- Modify: `VERSION`
- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: The tested About layout.
- Produces: A corrected v2026.7.2 protected-branch merge commit, moved annotated tag, updated GitHub release, and republished container image.

- [x] **Step 1: Validate the rendered dark-mode page without screenshots**

Run the local web application and inspect `/cookdex/about` in Playwright at a
wide desktop viewport and a narrow viewport. Confirm page identity, meaningful
content, no framework overlay, no relevant console errors, correct card
positions, no clipping, and working navigation between About and one other
page. Do not invoke screenshot capture.

- [x] **Step 2: Run all quality gates**

Run:

```bash
python3 -m pytest -q
python3 -m ruff check src tests
python3 -m bandit -r src -ll -b .bandit-baseline.json
node --test web/tests/AboutPage.test.mjs
npm --prefix web run build:docker
git diff --check
```

Expected: every command exits successfully.

- [x] **Step 3: Keep v2026.7.2 metadata**

Keep `VERSION`, `web/package.json`, and the root entries in
`web/package-lock.json` at `2026.7.2`. Add the fixed About-page card gap and
browser geometry regression coverage to the existing dated `2026.7.2`
changelog section.

- [ ] **Step 4: Commit, push, and merge through the protected branch**

Commit the complete hotfix, push `codex/fix-about-layout`, open a pull request,
wait for required checks, and squash-merge it into `main`.

- [ ] **Step 5: Tag, release, and verify publishing**

Move and push annotated tag `v2026.7.2` to the corrected merge commit, update
the existing GitHub release, wait for the tag's container workflow to finish,
confirm the release points to the merged commit, run `bd sync` if a Beads
database is available, and verify local `main` is clean and up to date with
`origin/main`.
