# Forked Cross-Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a restrained Forked promotion to CookDex's About page and README.

**Architecture:** Keep both placements static and dependency-free. The React About page receives one additional card using existing presentation components and styles, while the README receives a short introductory mention; a Vite-powered Node test renders the real component and verifies its user-visible contract.

**Tech Stack:** React 18 JSX, React DOM server rendering, Node test runner, existing CookDex CSS and `Icon` component, Markdown, pytest, Vite 8.

## Global Constraints

- Add exactly two placements: the About-page card and the near-top README mention.
- Use `https://apps.apple.com/us/app/forked-recipes/id6760947117` for both links.
- Present Forked as “Also from Knownframe,” not as a recommendation or dependency.
- Use existing CookDex card, paragraph, icon, and link-button patterns.
- Do not add artwork, animation, accent styling, banners, modals, onboarding prompts, badges, analytics, API data, backend configuration, assets, or application state.
- Open the About-page App Store link in a new tab with `rel="noreferrer"`.

---

### Task 1: Add the Forked About-page card

**Files:**
- Create: `web/tests/AboutPage.test.mjs`
- Modify: `web/src/pages/about/AboutPage.jsx`

**Interfaces:**
- Consumes: Existing `Icon` component names `external`, existing CSS classes `card`, `privacy-detail`, and `link-btn`.
- Produces: Static semantic JSX for the Forked promotion; no new props, exports, state, or API interfaces.

- [x] **Step 1: Write the failing rendered-component regression test**

Create `web/tests/AboutPage.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(TEST_DIR, "..");
const APP_STORE_URL = "https://apps.apple.com/us/app/forked-recipes/id6760947117";

test("About page renders the Forked card between privacy and project links", async (t) => {
  globalThis.window = {
    location: { hostname: "localhost", pathname: "/cookdex/about" },
  };
  t.after(() => {
    delete globalThis.window;
  });

  const vite = await createServer({
    root: WEB_ROOT,
    server: { middlewareMode: true },
    appType: "custom",
    logLevel: "silent",
  });
  t.after(async () => {
    await vite.close();
  });

  const { default: AboutPage } = await vite.ssrLoadModule(
    "/src/pages/about/AboutPage.jsx"
  );
  const html = renderToStaticMarkup(
    React.createElement(AboutPage, {
      aboutMeta: { app_version: "test" },
      healthMeta: { ok: true },
      lastLoadedAt: "",
    })
  );

  assert.ok(html.includes("Also from Knownframe"));
  assert.ok(html.includes("<strong>Forked</strong>"));
  assert.ok(html.includes("Swipe-based discovery, dietary filtering, meal plans"));
  assert.ok(html.includes("Free on the App Store."));
  assert.ok(html.includes("View on the App Store"));
  assert.ok(html.includes(`href="${APP_STORE_URL}"`));
  assert.ok(html.includes('target="_blank"'));
  assert.ok(html.includes('rel="noreferrer"'));
  assert.ok(
    html.indexOf("Privacy &amp; Data") < html.indexOf("Also from Knownframe")
  );
  assert.ok(html.indexOf("Also from Knownframe") < html.indexOf("Project Links"));
});
```

- [x] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
node --test web/tests/AboutPage.test.mjs
```

Expected: `FAIL` at the “Also from Knownframe” assertion because the rendered
About page does not yet contain the Forked card.

- [x] **Step 3: Add the minimal About-page card**

Insert this card in `web/src/pages/about/AboutPage.jsx` immediately after the
**Privacy & Data** card and before the **Project Links** card:

```jsx
        <article className="card">
          <h3><Icon name="external" /> Also from Knownframe</h3>
          <p className="privacy-detail">
            <strong>Forked</strong> — a native iOS app for deciding what to
            cook from your Mealie library. Swipe-based discovery, dietary
            filtering, meal plans, and one persistent shopping list.
          </p>
          <p className="privacy-detail">
            Free on the App Store. A clean, well-tagged library makes it
            noticeably better.
          </p>
          <a
            className="link-btn"
            href="https://apps.apple.com/us/app/forked-recipes/id6760947117"
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="external" />
            View on the App Store
          </a>
        </article>
```

- [x] **Step 4: Run the focused test and confirm it passes**

Run:

```bash
node --test web/tests/AboutPage.test.mjs
```

Expected: `PASS`.

- [x] **Step 5: Build the web application**

Run:

```bash
npm --prefix web run build:docker
```

Expected: Vite completes successfully and writes the production bundle.

- [x] **Step 6: Commit the About-page placement**

Run:

```bash
git add web/tests/AboutPage.test.mjs web/src/pages/about/AboutPage.jsx
git commit -m "Add Forked promotion to About page"
```

---

### Task 2: Add the Forked README mention

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: The public Forked App Store URL and the README's existing two-paragraph introduction.
- Produces: A static Markdown link near the top of the README; no code interface.

- [x] **Step 1: Add the minimal README mention**

Add this paragraph immediately after the README's second introductory paragraph
and before `## What It Actually Does`:

```markdown
A clean library also makes native Mealie clients better.
[Forked](https://apps.apple.com/us/app/forked-recipes/id6760947117), also from
Knownframe, turns your recipes into swipe-based discovery, meal plans, and one
persistent shopping list.
```

- [x] **Step 2: Review the rendered Markdown source placement**

Run:

```bash
sed -n '1,30p' README.md
```

Expected: The Forked paragraph appears after the two introductory paragraphs and
before `## What It Actually Does`, with the exact App Store URL. Human-facing
prose is reviewed directly rather than pinned with a source-text regression
test.

- [x] **Step 3: Run all regression tests and the production web build**

Run:

```bash
python3 -m pytest -q
node --test web/tests/AboutPage.test.mjs
npm --prefix web run build:docker
```

Expected: The complete pytest suite and rendered About-page test pass, and Vite
completes successfully.

- [x] **Step 4: Commit the README placement**

Run:

```bash
git add README.md
git commit -m "Mention Forked in README"
```

---

### Task 3: Verify and publish the feature branch

**Files:**
- Verify only: all files committed by Tasks 1 and 2.

**Interfaces:**
- Consumes: The two tested feature commits.
- Produces: A clean feature branch pushed to `origin/codex/forked-cross-promotion`.

- [ ] **Step 1: Confirm formatting and repository cleanliness**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: No whitespace errors and no uncommitted feature files.

- [ ] **Step 2: Rebase onto the current remote branch**

Run:

```bash
git pull --rebase
```

Expected: The branch is current or rebases without conflicts.

- [ ] **Step 3: Synchronize the project tracker if available**

Run:

```bash
bd sync
```

Expected in this checkout: the command reports that no Beads database exists.
Do not initialize a tracker implicitly.

- [ ] **Step 4: Push the completed branch**

Run:

```bash
git push
```

Expected: `origin/codex/forked-cross-promotion` advances to the final commit.

- [ ] **Step 5: Confirm remote synchronization**

Run:

```bash
git status --short --branch
```

Expected: The branch is clean and up to date with
`origin/codex/forked-cross-promotion`.
