# Forked Cross-Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a restrained Forked promotion to CookDex's About page and README.

**Architecture:** Keep both placements static and dependency-free. The React About page receives one additional card using existing presentation components and styles, while the README receives a short introductory mention; source-level regression tests pin the approved copy, placement, and destination.

**Tech Stack:** React 18 JSX, existing CookDex CSS and `Icon` component, Markdown, pytest, Vite 8.

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
- Modify: `tests/test_webui_overview_page.py`
- Modify: `web/src/pages/about/AboutPage.jsx`

**Interfaces:**
- Consumes: Existing `Icon` component names `external`, existing CSS classes `card`, `privacy-detail`, and `link-btn`.
- Produces: Static semantic JSX for the Forked promotion; no new props, exports, state, or API interfaces.

- [ ] **Step 1: Write the failing About-page regression test**

Add this test to `tests/test_webui_overview_page.py`:

```python
def test_about_promotes_forked_between_privacy_and_project_links():
    about_source = (
        REPO_ROOT / "web" / "src" / "pages" / "about" / "AboutPage.jsx"
    ).read_text(encoding="utf-8")
    app_store_url = "https://apps.apple.com/us/app/forked-recipes/id6760947117"

    assert "Also from Knownframe" in about_source
    assert "<strong>Forked</strong>" in about_source
    assert "Swipe-based discovery, dietary filtering, meal plans, and one" in about_source
    assert "Free on the App Store." in about_source
    assert "View on the App Store" in about_source
    assert app_store_url in about_source
    assert about_source.index("Privacy &amp; Data") < about_source.index(
        "Also from Knownframe"
    ) < about_source.index("Project Links")
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
pytest tests/test_webui_overview_page.py::test_about_promotes_forked_between_privacy_and_project_links -v
```

Expected: `FAIL` because `AboutPage.jsx` does not yet contain “Also from Knownframe.”

- [ ] **Step 3: Add the minimal About-page card**

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

- [ ] **Step 4: Run the focused test and confirm it passes**

Run:

```bash
pytest tests/test_webui_overview_page.py::test_about_promotes_forked_between_privacy_and_project_links -v
```

Expected: `PASS`.

- [ ] **Step 5: Build the web application**

Run:

```bash
npm --prefix web run build:docker
```

Expected: Vite completes successfully and writes the production bundle.

- [ ] **Step 6: Commit the About-page placement**

Run:

```bash
git add tests/test_webui_overview_page.py web/src/pages/about/AboutPage.jsx
git commit -m "Add Forked promotion to About page"
```

---

### Task 2: Add the Forked README mention

**Files:**
- Modify: `tests/test_documentation_accuracy.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: The public Forked App Store URL and the README's existing two-paragraph introduction.
- Produces: A static Markdown link near the top of the README; no code interface.

- [ ] **Step 1: Write the failing README regression test**

Add this test to `tests/test_documentation_accuracy.py`:

```python
def test_readme_promotes_forked_near_the_introduction() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    introduction = " ".join(
        readme.split("## What It Actually Does", maxsplit=1)[0].split()
    )

    assert "A clean library also makes native Mealie clients better." in introduction
    assert "Forked" in introduction
    assert "also from Knownframe" in introduction
    assert "swipe-based discovery, meal plans, and one persistent shopping list" in introduction
    assert "https://apps.apple.com/us/app/forked-recipes/id6760947117" in introduction
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
pytest tests/test_documentation_accuracy.py::test_readme_promotes_forked_near_the_introduction -v
```

Expected: `FAIL` because the README introduction does not yet mention Forked.

- [ ] **Step 3: Add the minimal README mention**

Add this paragraph immediately after the README's second introductory paragraph
and before `## What It Actually Does`:

```markdown
A clean library also makes native Mealie clients better.
[Forked](https://apps.apple.com/us/app/forked-recipes/id6760947117), also from
Knownframe, turns your recipes into swipe-based discovery, meal plans, and one
persistent shopping list.
```

- [ ] **Step 4: Run the focused test and confirm it passes**

Run:

```bash
pytest tests/test_documentation_accuracy.py::test_readme_promotes_forked_near_the_introduction -v
```

Expected: `PASS`.

- [ ] **Step 5: Run all regression tests and the production web build**

Run:

```bash
pytest -q
npm --prefix web run build:docker
```

Expected: The complete pytest suite passes and Vite completes successfully.

- [ ] **Step 6: Commit the README placement**

Run:

```bash
git add README.md tests/test_documentation_accuracy.py
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
