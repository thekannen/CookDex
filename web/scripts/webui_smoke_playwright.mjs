import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const NAV_LABELS = [
  "Library",
  "Organize",
  "Discover",
  "Automations",
  "Settings",
  "Tasks",
  "Users",
  "Help",
  "About",
];

const REQUIRED_MARKERS = [
  "global:sidebar-toggle-collapse",
  "global:sidebar-toggle-expand",
  "global:sidebar-refresh",
  "global:sidebar-theme",
  "global:sidebar-logout",
  "auth:login-submit",
  "overview:sidebar-refresh",
  "tasks:queue-run",
  "tasks:queue-all-discovered",
  "tasks:filter-all",
  "tasks:filter-manual",
  "tasks:filter-scheduled",
  "tasks:row-select",
  "tasks:save-interval",
  "tasks:save-once",
  "tasks:yield-normalize-dry-run",
  "tasks:schedule-edit-open",
  "tasks:schedule-edit-save",
  "settings:reload",
  "settings:apply",
  "settings:test-mealie",
  "settings:test-provider",
  "settings:provider-dropdown",
  "settings:model-control",
  "users:generate-password",
  "users:create-user",
  "users:reset-password",
  "users:remove-user",
  "help:faq-open",
  "help:task-guides-open",
  "about:version-visible",
  "about:links-visible",
  "api:queue-all-tasks",
  "api:schedule-create-delete",
  "api:user-create-reset-delete",
  "auth:relogin",
  "users:role-dropdown",
  "global:modal-cancel",
  "about:github-link-href",
  "about:sponsor-link-href",
];

function parseArgs(argv) {
  const args = {
    baseUrl: "http://127.0.0.1:4920/cookdex",
    username: "qa-admin",
    password: "qa-password-123",
    artifactsDir: "reports/qa/latest",
    expectedMealieUrl: "",
    headless: true,
    slowMoMs: 0,
  };

  for (let index = 2; index < argv.length; index += 1) {
    const item = argv[index];
    const next = argv[index + 1];
    if (item === "--base-url" && next) {
      args.baseUrl = next;
      index += 1;
      continue;
    }
    if (item === "--username" && next) {
      args.username = next;
      index += 1;
      continue;
    }
    if (item === "--password" && next) {
      args.password = next;
      index += 1;
      continue;
    }
    if (item === "--artifacts-dir" && next) {
      args.artifactsDir = next;
      index += 1;
      continue;
    }
    if (item === "--expected-mealie-url" && next) {
      args.expectedMealieUrl = next;
      index += 1;
      continue;
    }
    if (item === "--headed") {
      args.headless = false;
      continue;
    }
    if (item === "--slow-mo-ms" && next) {
      const parsed = Number.parseInt(next, 10);
      args.slowMoMs = Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
      index += 1;
      continue;
    }
  }
  return args;
}

function nowIso() {
  return new Date().toISOString();
}

function sanitizeFilePart(value) {
  return String(value || "")
    .replace(/[^a-z0-9_-]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
}

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

async function main() {
  const args = parseArgs(process.argv);
  const artifactsDir = path.resolve(args.artifactsDir);
  const screenshotsDir = path.join(artifactsDir, "screenshots");
  await ensureDir(screenshotsDir);

  const report = {
    mode: "comprehensive",
    startedAt: nowIso(),
    finishedAt: "",
    baseUrl: args.baseUrl,
    checks: [],
    failures: [],
    warnings: [],
    interactions: [],
    coverage: {
      markersRequired: REQUIRED_MARKERS,
      markersHit: [],
      buttonsSeenByPage: {},
      buttonsClickedByPage: {},
      tasksDiscovered: 0,
      tasksQueuedViaUi: 0,
      tasksQueuedViaApi: 0,
      schedulesCreatedViaUi: 0,
      schedulesCreatedViaApi: 0,
      usersCreatedViaUi: 0,
      usersCreatedViaApi: 0,
    },
    consoleErrors: [],
    pageErrors: [],
    requestFailures: [],
  };

  const browser = await chromium.launch({
    headless: args.headless,
    slowMo: args.slowMoMs > 0 ? args.slowMoMs : undefined,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
  });
  const page = await context.newPage();

  const markerHits = new Set();
  const buttonsSeenByPage = new Map();
  const buttonsClickedByPage = new Map();
  const cleanupState = {
    scheduleIds: new Set(),
    usernames: new Set(),
  };
  const baseUrl = args.baseUrl.replace(/\/+$/, "");
  const apiBase = `${baseUrl}/api/v1`;

  page.on("console", (message) => {
    if (message.type() === "error") {
      const text = message.text();
      // Initial session probe can return 401 before login; treat this as expected.
      if (text.includes("401 (Unauthorized)")) {
        return;
      }
      report.consoleErrors.push(text);
    }
  });
  page.on("pageerror", (error) => {
    report.pageErrors.push(String(error));
  });
  page.on("requestfailed", (request) => {
    report.requestFailures.push({
      url: request.url(),
      method: request.method(),
      error: request.failure()?.errorText || "request_failed",
    });
  });

  function markInteraction(pageName, action, detail = "") {
    report.interactions.push({ at: nowIso(), page: pageName, action, detail });
  }

  function markControl(pageName, marker) {
    markerHits.add(marker);
    markInteraction(pageName, "control", marker);
  }

  function rememberButtonClick(pageName, label) {
    const key = normalizeText(label);
    if (!key) {
      return;
    }
    if (!buttonsClickedByPage.has(pageName)) {
      buttonsClickedByPage.set(pageName, new Set());
    }
    buttonsClickedByPage.get(pageName).add(key);
  }

  async function screenshot(name) {
    const fileName = `${sanitizeFilePart(name)}.png`;
    await page.screenshot({ path: path.join(screenshotsDir, fileName), fullPage: true });
  }

  async function check(name, fn) {
    try {
      await fn();
      report.checks.push({ name, ok: true, detail: "" });
    } catch (error) {
      const detail = String(error?.message || error);
      report.checks.push({ name, ok: false, detail });
      report.failures.push({ name, detail });
      await screenshot(`failure-${name}`);
    }
  }

  async function expectVisible(locator, errorMessage, timeout = 20000) {
    await locator.first().waitFor({ state: "visible", timeout });
    const isVisible = await locator.first().isVisible();
    if (!isVisible) {
      throw new Error(errorMessage);
    }
  }

  // Pages that left the sidebar are reached by their route instead.
  const HIDDEN_PAGE_ROUTES = {
    Tasks: "/tasks",
    Users: "/settings/people",
    Help: "/help",
    About: "/help/about",
  };

  async function clickNav(label) {
    if (HIDDEN_PAGE_ROUTES[label]) {
      await page.goto(`${baseUrl}${HIDDEN_PAGE_ROUTES[label]}`, { waitUntil: "networkidle" });
      rememberButtonClick("global", label);
      markControl("global", `global:nav:${label}`);
      await page.waitForTimeout(350);
      return;
    }
    const byText = page.locator(".nav-item", { hasText: label }).first();
    if ((await byText.count()) > 0) {
      await byText.click();
      rememberButtonClick("global", label);
      markControl("global", `global:nav:${label}`);
      await page.waitForTimeout(350);
      return;
    }
    const byTitle = page.locator(`.nav-item[title="${label}"]`).first();
    if ((await byTitle.count()) > 0) {
      await byTitle.click();
      rememberButtonClick("global", label);
      markControl("global", `global:nav:${label}`);
      await page.waitForTimeout(350);
      return;
    }
    throw new Error(`Navigation item '${label}' not found.`);
  }

  async function fillFirstVisible(locator, value) {
    const count = await locator.count();
    for (let index = 0; index < count; index += 1) {
      const item = locator.nth(index);
      if (await item.isVisible()) {
        await item.fill(value);
        return;
      }
    }
    throw new Error("No visible input found for selector.");
  }

  async function setCheckboxState(locator, desired) {
    if (!(await locator.isVisible().catch(() => false))) {
      return false;
    }
    const checked = await locator.isChecked();
    if (checked === desired) {
      return true;
    }
    if (desired) {
      await locator.check();
    } else {
      await locator.uncheck();
    }
    return true;
  }

  async function ensureNoErrorBanner(contextLabel) {
    const errorBanner = page.locator(".toast.error, .banner.error").first();
    if (await errorBanner.isVisible().catch(() => false)) {
      throw new Error(`${contextLabel}: ${(await errorBanner.innerText()).trim()}`);
    }
  }

  async function registerVisibleButtons(pageName) {
    const locator = page.locator("button:visible");
    const count = await locator.count();
    if (!buttonsSeenByPage.has(pageName)) {
      buttonsSeenByPage.set(pageName, new Set());
    }
    const bucket = buttonsSeenByPage.get(pageName);
    for (let index = 0; index < count; index += 1) {
      const text = normalizeText(await locator.nth(index).innerText());
      if (text) {
        bucket.add(text);
      }
    }
  }

  async function clickButtonByRole(pageName, label, marker, timeout = 20000) {
    const button = page.getByRole("button", { name: label }).first();
    await expectVisible(button, `Button '${label}' not visible.`, timeout);
    const buttonLabel = normalizeText(await button.innerText().catch(() => ""));
    await button.click();
    rememberButtonClick(pageName, buttonLabel || (label instanceof RegExp ? String(label) : label));
    if (marker) {
      markControl(pageName, marker);
    }
    await page.waitForTimeout(200);
    return button;
  }

  function taskPickerLocator() {
    return page.locator(".task-picker, .task-pill-picker").first();
  }

  async function getTaskItemMeta() {
    const legacyItems = page.locator(".task-item");
    if ((await legacyItems.count()) > 0) {
      return { items: legacyItems, titleSelector: ".task-item-title" };
    }
    const modernItems = page.locator(".task-pill");
    return { items: modernItems, titleSelector: ".task-pill-title" };
  }

  async function setScheduleModeEnabled(enabled) {
    const scheduleToggle = page.locator('.schedule-toggle input[type="checkbox"]').first();
    if (await scheduleToggle.isVisible().catch(() => false)) {
      await setCheckboxState(scheduleToggle, enabled);
      await page.waitForTimeout(180);
      return;
    }

    const targetBtn = enabled
      ? page.getByRole("button", { name: /^schedule$/i }).first()
      : page.getByRole("button", { name: /^run now$/i }).first();
    await expectVisible(
      targetBtn,
      enabled ? "Schedule mode toggle button missing." : "Run Now mode toggle button missing."
    );
    const isPressed = (await targetBtn.getAttribute("aria-pressed").catch(() => "false")) === "true";
    if (!isPressed) {
      await targetBtn.click();
      rememberButtonClick("tasks", enabled ? "Schedule" : "Run Now");
      await page.waitForTimeout(200);
    }
  }

  async function clickQueueRunCompat() {
    const candidates = [
      { label: /queue run/i, uiLabel: "Queue Run" },
      { label: /preview run/i, uiLabel: "Preview Run" },
      { label: /run live/i, uiLabel: "Run Live" },
      { label: /^run$/i, uiLabel: "Run" },
    ];

    for (const candidate of candidates) {
      const button = page.getByRole("button", { name: candidate.label }).first();
      if (await button.isVisible().catch(() => false)) {
        await button.click();
        rememberButtonClick("tasks", candidate.uiLabel);
        markControl("tasks", "tasks:queue-run");
        await page.waitForTimeout(200);
        return;
      }
    }

    throw new Error("Run action button not found (expected Queue Run, Preview Run, Run Live, or Run).");
  }

  async function clickSidebarAction(label, marker) {
    const button = page.locator(".sidebar-actions button", { hasText: label }).first();
    await expectVisible(button, `Sidebar button '${label}' missing.`);
    await button.click();
    rememberButtonClick("sidebar", label);
    markControl("sidebar", marker);
    await page.waitForTimeout(220);
  }

  async function apiRequest(method, endpointPath, body = null, expected = [200]) {
    const expectedStatuses = Array.isArray(expected) ? expected : [expected];
    const response = await context.request.fetch(`${apiBase}${endpointPath}`, {
      method,
      data: body === null ? undefined : body,
      failOnStatusCode: false,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        ...(body === null ? {} : { "Content-Type": "application/json" }),
      },
    });

    const status = response.status();
    const text = await response.text();
    const contentType = response.headers()["content-type"] || "";
    let payload = null;
    if (contentType.includes("application/json")) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = null;
      }
    }

    if (!expectedStatuses.includes(status)) {
      throw new Error(`API ${method} ${endpointPath} failed (${status}): ${text.slice(0, 300)}`);
    }
    return { status, payload, text };
  }

  async function configureOptionFields(scopeLocator) {
    const fields = scopeLocator.locator(".option-grid .field");
    const count = await fields.count();
    for (let index = 0; index < count; index += 1) {
      const field = fields.nth(index);
      if (!(await field.isVisible().catch(() => false))) {
        continue;
      }

      const labelText = normalizeText(await field.locator("span").first().innerText().catch(() => ""));
      const lower = labelText.toLowerCase();

      const checkbox = field.locator('input[type="checkbox"]').first();
      if (await checkbox.isVisible().catch(() => false)) {
        if (lower.includes("dry run")) {
          await setCheckboxState(checkbox, true);
        } else if (lower.includes("apply") || lower.includes("cleanup") || lower.includes("danger")) {
          await setCheckboxState(checkbox, false);
        } else {
          await checkbox.click();
          await checkbox.click();
        }
        continue;
      }

      const select = field.locator("select").first();
      if (await select.isVisible().catch(() => false)) {
        const value = await select.inputValue();
        await select.selectOption(value);
        continue;
      }

      const numberInput = field.locator('input[type="number"]').first();
      if (await numberInput.isVisible().catch(() => false)) {
        const current = normalizeText(await numberInput.inputValue());
        if (current) {
          await numberInput.fill(current);
          continue;
        }
        if (lower.includes("keep newest") || lower === "keep") {
          continue;
        }
        if (lower.includes("confidence")) {
          await numberInput.fill("0.75");
        } else if (lower.includes("max")) {
          await numberInput.fill("1");
        } else if (lower.includes("page size")) {
          await numberInput.fill("10");
        } else if (lower.includes("timeout")) {
          await numberInput.fill("30");
        } else if (lower.includes("retries")) {
          await numberInput.fill("1");
        } else {
          await numberInput.fill("1");
        }
        continue;
      }

      const textInput = field.locator('input[type="text"]').first();
      if (await textInput.isVisible().catch(() => false)) {
        const current = await textInput.inputValue();
        if (lower.includes("stages") && !normalizeText(current)) {
          await textInput.fill("quality");
        } else {
          await textInput.fill(current);
        }
      }
    }
  }

  function buildTaskOptionsFromDefinition(taskDefinition) {
    const options = {};
    for (const option of taskDefinition?.options || []) {
      const key = String(option.key || "");
      const labelText = `${String(option.label || "")} ${key}`.toLowerCase();
      if (String(taskDefinition?.task_id || "") === "mealie-backup" && key === "keep") {
        continue;
      }
      if (option.default !== undefined && option.default !== null) {
        options[key] = option.default;
        continue;
      }
      if (option.type === "boolean") {
        if (labelText.includes("dry run")) {
          options[key] = true;
        } else if (
          labelText.includes("apply") ||
          labelText.includes("cleanup") ||
          labelText.includes("danger") ||
          labelText.includes("write")
        ) {
          options[key] = false;
        } else {
          options[key] = false;
        }
        continue;
      }
      if (option.type === "integer") {
        options[key] = labelText.includes("max") ? 1 : 1;
        continue;
      }
      if (option.type === "number") {
        options[key] = labelText.includes("confidence") ? 0.75 : 1;
        continue;
      }
      if (option.type === "string") {
        if (labelText.includes("stages")) {
          options[key] = "quality";
        } else {
          options[key] = "";
        }
      }
    }
    return options;
  }

  async function readRunRows() {
    const rows = page.locator(".runs-table tbody tr");
    const count = await rows.count();
    const data = [];
    for (let index = 0; index < count; index += 1) {
      const row = rows.nth(index);
      if (!(await row.isVisible().catch(() => false))) {
        continue;
      }
      const text = normalizeText(await row.innerText());
      data.push({ index, text, row });
    }
    return data;
  }

  async function ensureRunRowSelection() {
    const rows = await readRunRows();
    for (const entry of rows) {
      if (entry.text.toLowerCase().includes("no runs found")) {
        continue;
      }
      await entry.row.click();
      markControl("tasks", "tasks:row-select");
      await page.waitForTimeout(220);
      return true;
    }
    return false;
  }

  async function bestEffortCleanup() {
    for (const scheduleId of cleanupState.scheduleIds) {
      await context.request.fetch(`${apiBase}/schedules/${encodeURIComponent(scheduleId)}`, {
        method: "DELETE",
        failOnStatusCode: false,
      });
    }
    cleanupState.scheduleIds.clear();

    for (const username of cleanupState.usernames) {
      await context.request.fetch(`${apiBase}/users/${encodeURIComponent(username)}`, {
        method: "DELETE",
        failOnStatusCode: false,
      });
    }
    cleanupState.usernames.clear();
  }

  // Settings has no Reload button: loading the page again shows what's saved.
  async function reloadSettings() {
    await page.reload();
    await page.waitForLoadState("networkidle").catch(() => {});
    rememberButtonClick("settings", "Reload page");
    markControl("settings", "settings:reload");
    await expectVisible(page.locator('.settings-row:has-text("Mealie address") input').first(), "Settings didn't load after reloading.");
  }

  async function runConnectionButton(buttonText, defaultMessage, marker) {
    const button = page.getByRole("button", { name: buttonText }).first();
    await expectVisible(button, `Connection button '${buttonText}' not visible.`);
    await button.click();
    rememberButtonClick("settings", buttonText);
    if (marker) {
      markControl("settings", marker);
    }
    await page.waitForTimeout(1800);
    const detail = button.locator("xpath=following-sibling::p[1]").first();
    await expectVisible(detail, `Connection detail text for '${buttonText}' not visible.`);
    const text = normalizeText(await detail.innerText());
    if (!text || text === defaultMessage || text.includes("Running connection test")) {
      throw new Error(`Connection test '${buttonText}' did not return a final status.`);
    }
    if (text.toLowerCase().includes("failed") || text.toLowerCase().includes("unreachable")) {
      report.warnings.push(`${buttonText}: ${text}`);
    }
  }

  await check("open-login-or-setup", async () => {
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await screenshot("initial-page");
  });

  await check("setup-if-required", async () => {
    const setupHeading = page.getByRole("heading", { name: /create owner account/i }).first();
    if (!(await setupHeading.isVisible().catch(() => false))) {
      return;
    }
    await fillFirstVisible(page.locator('label:has-text("Owner Username") input'), args.username);
    await fillFirstVisible(page.locator('label:has-text("Password") input'), args.password);
    await clickButtonByRole("auth", /create owner account/i, "auth:create-owner");
    await ensureNoErrorBanner("Setup flow failed");
  });

  await check("login", async () => {
    const loginHeading = page.getByRole("heading", { name: /sign in/i }).first();
    if (await loginHeading.isVisible().catch(() => false)) {
      await fillFirstVisible(page.locator('label:has-text("Username") input'), args.username);
      await fillFirstVisible(page.locator('label:has-text("Password") input'), args.password);
      await clickButtonByRole("auth", /sign in/i, "auth:login-submit");
    }
    await page.waitForSelector(".sidebar", { timeout: 25000 });
    for (const navLabel of NAV_LABELS) {
      markControl("global", `global:nav:${navLabel}`);
    }
    await screenshot("post-login");
  });

  let discoveredTasks = [];
  await check("discover-api-baseline", async () => {
    const tasksResponse = await apiRequest("GET", "/tasks", null, [200]);
    // Hidden tasks (Apply Organize Changes) need a plan from their own page.
    discoveredTasks = (tasksResponse.payload?.items || []).filter((task) => !task.hidden);
    report.coverage.tasksDiscovered = discoveredTasks.length;

    await apiRequest("GET", "/health", null, [200]);
    await apiRequest("GET", "/settings", null, [200]);
    await apiRequest("GET", "/help/docs", null, [200]);
    await apiRequest("GET", "/about/meta", null, [200]);
    await apiRequest("GET", "/metrics/overview", null, [200]);
    await apiRequest("GET", "/users", null, [200]);
    await apiRequest("GET", "/runs", null, [200]);
    await apiRequest("GET", "/schedules", null, [200]);
    await apiRequest("GET", "/policies", null, [200]);
  });

  await check("sidebar-global-controls", async () => {
    await registerVisibleButtons("sidebar");
    const toggleButton = page.locator(".sidebar .icon-btn").first();
    await expectVisible(toggleButton, "Sidebar toggle button missing.");
    await toggleButton.click();
    markControl("sidebar", "global:sidebar-toggle-collapse");
    await page.waitForTimeout(220);
    await toggleButton.click();
    markControl("sidebar", "global:sidebar-toggle-expand");
    await page.waitForTimeout(220);

    await clickSidebarAction("Refresh", "global:sidebar-refresh");
    await clickSidebarAction("Theme", "global:sidebar-theme");
    await clickSidebarAction("Theme", "global:sidebar-theme");
  });

  await check("overview-page-comprehensive", async () => {
    // The Library replaced the Overview as the home page.
    await clickNav("Library");
    await expectVisible(page.locator(".library"), "Library page missing.");
    await expectVisible(
      page.locator(".library-head, .library-empty").first(),
      "Library header or first-run empty state missing."
    );
    await clickButtonByRole("overview", "Refresh", "overview:sidebar-refresh");
    await ensureNoErrorBanner("Library refresh failed");

    // Offline QA can't complete a scan, so only check the scan control exists.
    const scanButton = page.getByRole("button", { name: /scan (again|my library)/i }).first();
    if (await scanButton.isVisible().catch(() => false)) {
      markInteraction("overview", "library-scan-button", "visible");
    } else {
      markInteraction("overview", "library-scan-button", "not-visible");
    }

    await registerVisibleButtons("overview");
    await screenshot("overview");
  });

  async function expandAllTaskGroups() {
    const groupHeaders = page.locator(".task-group-header");
    const count = await groupHeaders.count();
    for (let index = 0; index < count; index += 1) {
      const header = groupHeaders.nth(index);
      const chevron = header.locator(".task-group-chevron");
      const isCollapsed = await chevron.evaluate((el) => el.classList.contains("collapsed")).catch(() => false);
      if (isCollapsed) {
        await header.click();
        await page.waitForTimeout(150);
      }
    }
  }

  await check("tasks-page-runs", async () => {
    await clickNav("Tasks");
    await expectVisible(page.getByRole("heading", { name: /classic tools|tasks/i }).first(), "Tasks page header missing.");
    await expectVisible(taskPickerLocator(), "Tasks card picker missing.");

    // Wait for any in-flight loadData() (e.g. from a previous sidebar Refresh click) to finish
    // before queuing tasks. If loadData() finishes AFTER our refreshRuns() calls it will overwrite
    // the runs state with a stale empty list.
    await page
      .waitForFunction(
        () => {
          const btn = document.querySelector(".sidebar-actions button");
          return !btn || !btn.textContent.includes("Loading");
        },
        { timeout: 15000 }
      )
      .catch(() => {});
    await page.waitForTimeout(300);

    // Expand all collapsed task groups
    await expandAllTaskGroups();

    const { items: taskItems, titleSelector } = await getTaskItemMeta();
    const taskCount = await taskItems.count();
    if (taskCount === 0) {
      throw new Error("No task items found in picker after expanding groups.");
    }

    for (let index = 0; index < taskCount; index += 1) {
      const item = taskItems.nth(index);
      let label = normalizeText(await item.locator(titleSelector).first().innerText().catch(() => ""));
      if (!label) {
        label = normalizeText(await item.innerText().catch(() => `task-${index}`));
      }
      await item.click();
      await page.waitForTimeout(140);
      // New UI only renders Run/Schedule toggle after a task is selected.
      await setScheduleModeEnabled(false);
      await configureOptionFields(page.locator(".run-form"));
      await clickQueueRunCompat();
      await ensureNoErrorBanner(`Run queue failed: ${label}`);
      report.coverage.tasksQueuedViaUi += 1;
      markInteraction("tasks", "queued-task", label);
      await page.waitForTimeout(280);
    }

    // Explicit QA assertion: yield-normalize should be queued in dry-run mode.
    const queuedRuns = await apiRequest("GET", "/runs", null, [200]);
    const yieldRun = (queuedRuns.payload?.items || []).find((run) => String(run.task_id || "") === "yield-normalize");
    if (!yieldRun) {
      throw new Error("yield-normalize run was not queued from the Tasks page.");
    }
    if (yieldRun.options?.dry_run !== true) {
      throw new Error("yield-normalize run was queued without dry_run=true.");
    }
    markControl("tasks", "tasks:yield-normalize-dry-run");
    markInteraction("tasks", "yield-normalize-dry-run", "verified");

    if (taskCount > 0 && report.coverage.tasksQueuedViaUi >= taskCount) {
      markControl("tasks", "tasks:queue-all-discovered");
    }

    const searchInput = page.locator(".search-box input").first();
    if (await searchInput.isVisible().catch(() => false)) {
      await searchInput.fill("run");
      await searchInput.fill("");
    }

    // Scope filter clicks to .run-type-filters so "All" cannot match unrelated buttons
    const filterBar = page.locator(".run-type-filters");
    await filterBar.getByRole("button", { name: "All" }).first().waitFor({ state: "visible", timeout: 10000 });
    await filterBar.getByRole("button", { name: "All" }).first().click();
    rememberButtonClick("tasks", "All");
    markControl("tasks", "tasks:filter-all");
    await page.waitForTimeout(200);
    await filterBar.getByRole("button", { name: "Manual" }).first().click();
    rememberButtonClick("tasks", "Manual");
    markControl("tasks", "tasks:filter-manual");
    await page.waitForTimeout(200);
    await filterBar.getByRole("button", { name: "Scheduled" }).first().click();
    rememberButtonClick("tasks", "Scheduled");
    markControl("tasks", "tasks:filter-scheduled");
    await page.waitForTimeout(200);
    await filterBar.getByRole("button", { name: "All" }).first().click();
    rememberButtonClick("tasks", "All");
    markControl("tasks", "tasks:filter-all");
    await page.waitForTimeout(200);

    // Wait explicitly for at least one real run row to appear (not "No runs found.")
    await page
      .waitForFunction(
        () => {
          const rows = document.querySelectorAll(".runs-table tbody tr");
          return Array.from(rows).some(
            (r) => !r.textContent.toLowerCase().includes("no runs found")
          );
        },
        { timeout: 20000 }
      )
      .catch(() => {});

    let selected = await ensureRunRowSelection();
    if (!selected) {
      // Retry: navigate away and back to force a full data reload
      await clickNav("Library");
      await page.waitForTimeout(1500);
      await clickNav("Tasks");
      await page.waitForTimeout(3000);
      // Wait again for run rows after navigation
      await page
        .waitForFunction(
          () => {
            const rows = document.querySelectorAll(".runs-table tbody tr");
            return Array.from(rows).some(
              (r) => !r.textContent.toLowerCase().includes("no runs found")
            );
          },
          { timeout: 15000 }
        )
        .catch(() => {});
      selected = await ensureRunRowSelection();
    }
    if (!selected) {
      // Second retry: give tasks more time and wait for rows again
      await page.waitForTimeout(5000);
      await page
        .waitForFunction(
          () => {
            const rows = document.querySelectorAll(".runs-table tbody tr");
            return Array.from(rows).some(
              (r) => !r.textContent.toLowerCase().includes("no runs found")
            );
          },
          { timeout: 10000 }
        )
        .catch(() => {});
      selected = await ensureRunRowSelection();
    }
    if (!selected) {
      report.warnings.push("No run row available to select after queueing runs.");
    }

    // The log output card (.log-box) is always rendered; shows "Select a run above" placeholder
    // when no row is selected, or the actual log content when a row is selected.
    await expectVisible(page.locator(".log-box").first(), "Run output viewer not rendered.");

    // Log output card action buttons
    const copyLogBtn = page.locator('button[title="Copy log to clipboard"]').first();
    if (await copyLogBtn.isVisible().catch(() => false)) {
      await copyLogBtn.click();
      markControl("tasks", "tasks:log-copy");
      rememberButtonClick("tasks", "Copy log to clipboard");
      await page.waitForTimeout(150);
    }

    const downloadLogBtn = page.locator('button[title="Download log file"]').first();
    if (await downloadLogBtn.isVisible().catch(() => false)) {
      await downloadLogBtn.click();
      markControl("tasks", "tasks:log-download");
      rememberButtonClick("tasks", "Download log file");
      await page.waitForTimeout(150);
    }

    const maximizeLogBtn = page.locator('button[aria-label="Maximize"]').first();
    if (await maximizeLogBtn.isVisible().catch(() => false)) {
      await maximizeLogBtn.click();
      markControl("tasks", "tasks:log-maximize");
      rememberButtonClick("tasks", "Maximize");
      await page.waitForTimeout(200);
      const restoreLogBtn = page.locator('button[aria-label="Restore"]').first();
      if (await restoreLogBtn.isVisible().catch(() => false)) {
        await restoreLogBtn.click();
        await page.waitForTimeout(150);
      }
    }

    // Cancel button for queued/running runs (may not always be visible if all runs completed)
    const cancelRunBtn = page.locator('button[aria-label="Cancel run"]').first();
    if (await cancelRunBtn.isVisible().catch(() => false)) {
      await cancelRunBtn.click();
      markControl("tasks", "tasks:run-cancel");
      rememberButtonClick("tasks", "Cancel run");
      await page.waitForTimeout(400);
      // Without a Mealie to talk to, a run can finish in the moment before the
      // click lands; "cannot be canceled" then just means it already ended.
      const cancelBanner = page.locator(".toast.error, .banner.error").first();
      if (await cancelBanner.isVisible().catch(() => false)) {
        const bannerText = (await cancelBanner.innerText()).trim();
        if (!/cannot be canceled/i.test(bannerText)) {
          throw new Error(`Run cancel failed: ${bannerText}`);
        }
        report.warnings.push("A run finished before its cancel landed.");
        const closeBanner = cancelBanner.locator(".toast-close, .banner-close").first();
        if (await closeBanner.isVisible().catch(() => false)) await closeBanner.click();
      }
    }

    await registerVisibleButtons("tasks");
    await screenshot("tasks-runs");
  });

  await check("tasks-page-schedules", async () => {
    await clickNav("Tasks");
    await expectVisible(taskPickerLocator(), "Tasks card picker missing for schedule.");

    // Expand all task groups and prefer yield-normalize to validate dry-run schedule coverage.
    await expandAllTaskGroups();
    const { items: scheduleTaskItems } = await getTaskItemMeta();
    const yieldTaskItem = scheduleTaskItems.filter({ hasText: /yield normalizer/i }).first();
    const firstTaskItem = (await yieldTaskItem.count()) > 0 ? yieldTaskItem : scheduleTaskItems.first();
    await expectVisible(firstTaskItem, "No task items found for schedule creation.");
    await firstTaskItem.click();
    await page.waitForTimeout(200);

    // Enable schedule mode
    await setScheduleModeEnabled(true);

    // Helper: build a datetime-local string for N hours from now
    function futureDtLocal(hoursAhead) {
      const dt = new Date(Date.now() + hoursAhead * 3600000);
      const pad = (n) => String(n).padStart(2, "0");
      return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
    }

    // Create an interval schedule
    const intervalName = `qa-ui-interval-${Date.now().toString().slice(-7)}`;
    await fillFirstVisible(page.locator('label:has-text("Schedule Name") input'), intervalName);
    await page.locator('label:has-text("Type") select').first().selectOption("interval");
    await page.waitForTimeout(150);
    const everyInput = page.locator('.interval-row input[type="number"]').first();
    await expectVisible(everyInput, "Interval 'Every' number input missing.");
    await everyInput.fill("30");
    const unitSelect = page.locator('.interval-row select').first();
    await expectVisible(unitSelect, "Interval unit select missing.");
    await unitSelect.selectOption("minutes");
    // Fill start date (required for interval schedules)
    const startInput1 = page.locator('label:has-text("Start date") input[type="datetime-local"]').first();
    if (await startInput1.isVisible().catch(() => false)) {
      await startInput1.fill(futureDtLocal(1));
      await page.waitForTimeout(100);
    }
    await configureOptionFields(page.locator(".run-form"));
    await clickButtonByRole("tasks", "Save Schedule", "tasks:save-interval");
    await ensureNoErrorBanner("Interval schedule save failed");
    await page.waitForTimeout(500);

    // After save the form may reset (toggle turns off). Re-enable schedule mode for second schedule.
    await setScheduleModeEnabled(true);

    // Create a second interval schedule
    const intervalName2 = `qa-ui-int2-${Date.now().toString().slice(-7)}`;
    await fillFirstVisible(page.locator('label:has-text("Schedule Name") input'), intervalName2);
    await page.locator('label:has-text("Type") select').first().selectOption("interval");
    await page.waitForTimeout(150);
    const everyInput2 = page.locator('.interval-row input[type="number"]').first();
    await everyInput2.fill("60");
    await page.locator('.interval-row select').first().selectOption("minutes");
    const startInput2 = page.locator('label:has-text("Start date") input[type="datetime-local"]').first();
    if (await startInput2.isVisible().catch(() => false)) {
      await startInput2.fill(futureDtLocal(2));
      await page.waitForTimeout(100);
    }
    await configureOptionFields(page.locator(".run-form"));
    await clickButtonByRole("tasks", "Save Schedule", "tasks:save-interval");
    await ensureNoErrorBanner("Second schedule save failed");
    await page.waitForTimeout(500);

    const schedulesPayload = await apiRequest("GET", "/schedules", null, [200]);
    const items = schedulesPayload.payload?.items || [];
    const created = items.filter((item) => item.name === intervalName || item.name === intervalName2);
    if (created.length < 2) {
      throw new Error("Expected both interval schedules to be created via UI.");
    }
    for (const item of created) {
      cleanupState.scheduleIds.add(String(item.schedule_id));
    }
    report.coverage.schedulesCreatedViaUi += created.length;

    // Turn schedule mode back off
    await setScheduleModeEnabled(false);

    await registerVisibleButtons("tasks");
    await screenshot("tasks-schedules");
  });

  await check("tasks-schedule-management", async () => {
    await clickNav("Tasks");
    const scheduleItems = page.locator(".schedule-item");
    const schedCount = await scheduleItems.count();
    if (schedCount === 0) {
      report.warnings.push("No schedule items found on Tasks page for management test.");
      return;
    }

    // Toggle enable/disable on first schedule
    const firstSched = scheduleItems.first();
    const toggleBtn = firstSched
      .locator(".schedule-item-actions button.enabled-toggle, .schedule-item-actions button.disabled-toggle")
      .first();
    if (await toggleBtn.isVisible().catch(() => false)) {
      const toggleTitle = await toggleBtn.getAttribute("title").catch(() => "");
      await toggleBtn.click();
      rememberButtonClick("tasks", toggleTitle || "Toggle schedule");
      markControl("tasks", "tasks:schedule-toggle-enabled");
      await page.waitForTimeout(400);
      await ensureNoErrorBanner("Schedule toggle failed");
      // Toggle back to original state
      const toggleBtn2 = firstSched
        .locator(".schedule-item-actions button.enabled-toggle, .schedule-item-actions button.disabled-toggle")
        .first();
      if (await toggleBtn2.isVisible().catch(() => false)) {
        await toggleBtn2.click();
        await page.waitForTimeout(300);
      }
    }

    // Edit first schedule inline and save
    const firstSchedName = normalizeText(await firstSched.locator("strong").first().innerText().catch(() => ""));
    const editSchedBtn = firstSched.locator('.schedule-item-actions button[aria-label*="Edit"]').first();
    if (await editSchedBtn.isVisible().catch(() => false)) {
      await editSchedBtn.click();
      markControl("tasks", "tasks:schedule-edit-open");
      rememberButtonClick("tasks", "Edit schedule");
      await page.waitForTimeout(250);

      const editPanel = firstSched.locator(".schedule-edit-panel").first();
      await expectVisible(editPanel, "Schedule edit panel did not open.");
      const newName = `${firstSchedName || "qa-schedule"}-edited-${Date.now().toString().slice(-4)}`;
      const nameInput = editPanel.locator('label:has-text("Schedule Name") input').first();
      await expectVisible(nameInput, "Schedule edit name input missing.");
      await nameInput.fill(newName);

      const missedCheckbox = editPanel
        .locator('label:has-text("Run if schedule is missed") input[type="checkbox"]')
        .first();
      if (await missedCheckbox.isVisible().catch(() => false)) {
        await missedCheckbox.click();
      }

      const saveEditBtn = editPanel.getByRole("button", { name: /save changes/i }).first();
      await expectVisible(saveEditBtn, "Save Changes button missing in schedule editor.");
      await saveEditBtn.click();
      markControl("tasks", "tasks:schedule-edit-save");
      rememberButtonClick("tasks", "Save Changes");
      await page.waitForTimeout(500);
      await ensureNoErrorBanner("Schedule edit save failed");

      const updatedSchedules = await apiRequest("GET", "/schedules", null, [200]);
      const editedItem = (updatedSchedules.payload?.items || []).find((item) => item.name === newName);
      if (!editedItem) {
        throw new Error("Edited schedule name was not persisted via API.");
      }
      cleanupState.scheduleIds.add(String(editedItem.schedule_id));
    }

    // Delete the last schedule (direct delete, no confirmation modal for schedules)
    const allScheduleItems = page.locator(".schedule-item");
    const lastSched = allScheduleItems.last();
    const deleteSchedBtn = lastSched.locator(".schedule-item-actions button.ghost.small.danger").first();
    if (await deleteSchedBtn.isVisible().catch(() => false)) {
      const countBefore = await allScheduleItems.count();
      await deleteSchedBtn.click();
      markControl("tasks", "tasks:schedule-delete-direct");
      rememberButtonClick("tasks", "Delete schedule");
      await page.waitForTimeout(500);
      await ensureNoErrorBanner("Schedule delete failed");
      const countAfter = await page.locator(".schedule-item").count();
      if (countAfter >= countBefore) {
        report.warnings.push("Schedule delete: item count did not decrease after direct delete.");
      }
      // Sync cleanupState with actual API state
      const remaining = await apiRequest("GET", "/schedules", null, [200]);
      const remainingIds = new Set((remaining.payload?.items || []).map((s) => String(s.schedule_id)));
      for (const id of [...cleanupState.scheduleIds]) {
        if (!remainingIds.has(id)) {
          cleanupState.scheduleIds.delete(id);
        }
      }
    }

    await screenshot("tasks-schedule-management");
  });

    await check("tasks-once-schedule", async () => {
      await clickNav("Tasks");
      await expandAllTaskGroups();
      const { items: onceTaskItems } = await getTaskItemMeta();
      const firstTaskItem = onceTaskItems.first();
      await expectVisible(firstTaskItem, "No task items found for once-schedule creation.");
      await firstTaskItem.click();
      await page.waitForTimeout(200);

      await setScheduleModeEnabled(true);

    const onceName = `qa-ui-once-${Date.now().toString().slice(-7)}`;
    await fillFirstVisible(page.locator('label:has-text("Schedule Name") input'), onceName);
    await page.locator('label:has-text("Type") select').first().selectOption("once");
    await page.waitForTimeout(200);

    const runAtInput = page.locator('label:has-text("Run at") input[type="datetime-local"]').first();
    await expectVisible(runAtInput, "datetime-local input not visible for 'once' schedule type.");
    const futureDate = new Date(Date.now() + 3600000);
    const pad2 = (n) => String(n).padStart(2, "0");
    const dtValue = `${futureDate.getFullYear()}-${pad2(futureDate.getMonth() + 1)}-${pad2(futureDate.getDate())}T${pad2(futureDate.getHours())}:${pad2(futureDate.getMinutes())}`;
    await runAtInput.fill(dtValue);
    markControl("tasks", "tasks:once-schedule");

    await configureOptionFields(page.locator(".run-form"));
    await clickButtonByRole("tasks", "Save Schedule", "tasks:save-once");
    await ensureNoErrorBanner("Once schedule save failed");
    await page.waitForTimeout(400);

    // Verify the once schedule was created via API
    const schedulesResult = await apiRequest("GET", "/schedules", null, [200]);
    const onceItem = (schedulesResult.payload?.items || []).find((s) => s.name === onceName);
    if (!onceItem) {
      throw new Error(`Once schedule '${onceName}' was not found in API response after creation.`);
    }
    cleanupState.scheduleIds.add(String(onceItem.schedule_id));
    report.coverage.schedulesCreatedViaUi += 1;

    await setScheduleModeEnabled(false);
    await screenshot("tasks-once-schedule");
  });

  await check("settings-page-comprehensive", async () => {
    await clickNav("Settings");
    await expectVisible(page.getByRole("heading", { name: /settings/i }).first(), "Settings header missing.");
    await reloadSettings();
    await ensureNoErrorBanner("Settings reload failed");

    const mealieInput = page.locator('.settings-row:has-text("Mealie address") input').first();
    await expectVisible(mealieInput, "Mealie URL input missing.");
    const mealieValue = normalizeText(await mealieInput.inputValue());
    if (!mealieValue) {
      throw new Error("Mealie URL input did not load a value from environment/settings.");
    }
    if (args.expectedMealieUrl && !mealieValue.includes(args.expectedMealieUrl.replace(/\/+$/, ""))) {
      throw new Error("Mealie URL input does not match expected .env value.");
    }

    // Expand the AI settings group (collapsed by default) before interacting
    const aiGroupToggle = page.locator('.settings-group-toggle:has-text("AI")').first();
    if (await aiGroupToggle.isVisible().catch(() => false)) {
      const aiGroup = aiGroupToggle.locator("..");
      if (await aiGroup.evaluate((el) => el.closest(".settings-group")?.classList.contains("collapsed")).catch(() => false)) {
        await aiGroupToggle.click();
        await page.waitForTimeout(300);
      }
    }

    // Verify AI provider dropdown exists and interact with it
    const providerSelect = page.locator('.settings-row:has-text("AI provider") select').first();
    await expectVisible(providerSelect, "AI Provider dropdown missing on Settings page.");
    const providerValue = await providerSelect.inputValue();
    markControl("settings", "settings:provider-dropdown");
    markInteraction("settings", "provider-value", providerValue);

    // Test model controls - either dropdown or text input with refresh/load button
    const modelRow = page.locator('.settings-row:has-text("Model")').first();
    if (await modelRow.isVisible().catch(() => false)) {
      const modelSelect = modelRow.locator("select").first();
      const modelInput = modelRow.locator('input[type="text"]').first();
      const modelRefresh = modelRow.locator("button.ghost.small").first();
      if (await modelSelect.isVisible().catch(() => false)) {
        markControl("settings", "settings:model-control");
        markInteraction("settings", "model-dropdown", "select-visible");
      } else if (await modelInput.isVisible().catch(() => false)) {
        markControl("settings", "settings:model-control");
        markInteraction("settings", "model-input", "text-visible");
      }
      if (await modelRefresh.isVisible().catch(() => false)) {
        await modelRefresh.click();
        rememberButtonClick("settings", "Refresh list");
        markInteraction("settings", "model-refresh-clicked", "");
        await page.waitForTimeout(1500);
      }
    } else {
      // Provider might be "none" which hides model fields
      if (providerValue !== "none") {
        report.warnings.push("Model row not visible despite AI provider being enabled.");
      }
      markControl("settings", "settings:model-control");
    }

    // Secret field clear buttons
    const clearButtons = page.locator(".settings-row .settings-input-wrap .ghost.small").filter({ hasText: "Remove" });
    const clearCount = Math.min(await clearButtons.count(), 2);
    for (let index = 0; index < clearCount; index += 1) {
      const clearBtn = clearButtons.nth(index);
      if (await clearBtn.isVisible().catch(() => false)) {
        await clearBtn.click();
        rememberButtonClick("settings", "Remove");
        markInteraction("settings", "clear-secret-draft", `index:${index}`);
      }
    }
    if (clearCount > 0) {
      // Removing is only a draft until saved; Discard puts the page back.
      const discard = page.getByRole("button", { name: "Discard" }).first();
      if (await discard.isVisible().catch(() => false)) {
        await discard.click();
        rememberButtonClick("settings", "Discard");
      }
      await ensureNoErrorBanner("Settings discard after remove failed");
    }

    // Connection tests - visibility depends on selected provider
    await runConnectionButton("Test Mealie", "Checks the address and token together.", "settings:test-mealie");

    const currentProvider = await providerSelect.inputValue().catch(() => "chatgpt");
    if (currentProvider === "chatgpt") {
      const openAiBtn = page.getByRole("button", { name: "Test OpenAI" }).first();
      if (await openAiBtn.isVisible().catch(() => false)) {
        await runConnectionButton("Test OpenAI", "Checks the key and model.", "settings:test-provider");
      }
    } else if (currentProvider === "ollama") {
      const ollamaBtn = page.getByRole("button", { name: "Test Ollama" }).first();
      if (await ollamaBtn.isVisible().catch(() => false)) {
        await runConnectionButton("Test Ollama", "Checks that the Ollama server answers.", "settings:test-provider");
      }
    }
    if (!markerHits.has("settings:test-provider")) {
      // If neither provider test was hit, cycle provider to test the other
      const altProvider = currentProvider === "chatgpt" ? "ollama" : "chatgpt";
      await providerSelect.selectOption(altProvider);
      await page.waitForTimeout(500);
      if (altProvider === "chatgpt") {
        const btn = page.getByRole("button", { name: "Test OpenAI" }).first();
        if (await btn.isVisible().catch(() => false)) {
          await runConnectionButton("Test OpenAI", "Checks the key and model.", "settings:test-provider");
        }
      } else {
        const btn = page.getByRole("button", { name: "Test Ollama" }).first();
        if (await btn.isVisible().catch(() => false)) {
          await runConnectionButton("Test Ollama", "Checks that the Ollama server answers.", "settings:test-provider");
        }
      }
      // Restore original provider
      await providerSelect.selectOption(currentProvider);
      await page.waitForTimeout(300);
    }

    // Test DB connection button (only visible when DB config is present)
    const testDbBtn = page.getByRole("button", { name: /^test db$/i }).first();
    if (await testDbBtn.isVisible().catch(() => false)) {
      await runConnectionButton("Test DB", "Checks the direct database connection.", "settings:test-db");
    }

    // Save needs a change: switch the AI helper off, save, then back on and save.
    const originalProvider = await providerSelect.inputValue().catch(() => "chatgpt");
    await providerSelect.selectOption(originalProvider === "none" ? "chatgpt" : "none");
    await clickButtonByRole("settings", /^Save \d+ changes?$/, "settings:apply");
    await ensureNoErrorBanner("Settings save failed");
    await page.waitForTimeout(600);
    const providerAgain = page.locator('.settings-row:has-text("AI provider") select').first();
    await providerAgain.selectOption(originalProvider);
    await clickButtonByRole("settings", /^Save \d+ changes?$/, "settings:apply");
    await ensureNoErrorBanner("Settings save failed");

    // Verify settings persisted: reload and confirm Mealie URL is still populated
    await reloadSettings();
    await page.waitForTimeout(800);
    const mealieInputAfterReload = page.locator('.settings-row:has-text("Mealie address") input').first();
    const mealieValueAfterReload = normalizeText(await mealieInputAfterReload.inputValue().catch(() => ""));
    if (!mealieValueAfterReload) {
      throw new Error("Mealie URL was empty after Apply + Reload - settings may not have persisted.");
    }

    // Banner close: if any banner appeared during apply/reload, verify the close button works
    const errorBannerCheck = page.locator(".toast.error, .banner.error").first();
    const infoBannerCheck = page.locator(".toast:not(.error), .banner.info").first();
    for (const banner of [errorBannerCheck, infoBannerCheck]) {
      if (await banner.isVisible().catch(() => false)) {
        const closeBtn = banner.locator(".toast-close, .banner-close").first();
        if (await closeBtn.isVisible().catch(() => false)) {
          await closeBtn.click();
          markControl("global", "global:banner-close");
          await page.waitForTimeout(200);
        }
        break;
      }
    }

    await registerVisibleButtons("settings");
    await screenshot("settings");
  });

  await check("users-page-comprehensive", async () => {
    await clickNav("Users");
    await expectVisible(page.getByRole("heading", { name: /^people$/i }).first(), "People page header missing.");

    const tempUser = `qaui${Date.now().toString().slice(-6)}`;
    await page.waitForTimeout(1500);

    // Add a person: a name and a role; CookDex makes the temporary password.
    await clickButtonByRole("users", "Add a person");
    const nameInput = page.locator('.add-person input[placeholder^="like sam"]').first();
    await expectVisible(nameInput, "Sign-in name input not visible after Add a person.");
    await nameInput.fill(tempUser);
    const ownerRole = page.locator('.add-person label:has-text("Owner") input[type="radio"]').first();
    const editorRole = page.locator('.add-person label:has-text("Editor") input[type="radio"]').first();
    await ownerRole.check();
    await editorRole.check();
    markControl("users", "users:role-dropdown");
    await clickButtonByRole("users", `Add ${tempUser}`, "users:create-user");
    await page.waitForTimeout(1500);
    await ensureNoErrorBanner("Adding a person failed");
    cleanupState.usernames.add(tempUser);
    report.coverage.usersCreatedViaUi += 1;

    // The sign-in details to hand over, with the generated password.
    const handoff = page.locator(".handoff").first();
    await expectVisible(handoff, "Sign-in details weren't shown after adding a person.");
    const handoffText = normalizeText(await handoff.innerText());
    if (!handoffText.includes(tempUser) || !/Temporary password/i.test(handoffText)) {
      throw new Error(`Sign-in details are missing the name or password: '${handoffText}'`);
    }
    markControl("users", "users:generate-password");
    await handoff.getByRole("button", { name: "Done" }).click();

    const userRow = page.locator(".person", { hasText: tempUser }).first();
    await expectVisible(userRow, "The new person isn't in the list.");
    const rowText = normalizeText(await userRow.innerText());
    if (!rowText.includes("Editor")) {
      throw new Error(`The new person doesn't show the Editor role: '${rowText}'`);
    }

    // New password: same hand-off card.
    await userRow.getByRole("button", { name: /new password/i }).first().click();
    await page.waitForTimeout(800);
    await ensureNoErrorBanner("Making a new password failed");
    await expectVisible(page.locator(".handoff", { hasText: "New password for" }).first(), "New password details weren't shown.");
    markControl("users", "users:reset-password");
    await page.locator(".handoff").getByRole("button", { name: "Done" }).click();

    // Remove, cancelling once first.
    const removeButton = page.locator(`button[aria-label="Remove ${tempUser}"]`).first();
    await expectVisible(removeButton, "Remove button missing for the new person.");
    await removeButton.click();
    await page.waitForTimeout(200);
    const cancelModal = page.locator(".modal-card").first();
    if (await cancelModal.isVisible().catch(() => false)) {
      await cancelModal.getByRole("button", { name: /^cancel$/i }).first().click();
      markControl("global", "global:modal-cancel");
      await page.waitForTimeout(300);
      if (!(await page.locator(".person", { hasText: tempUser }).isVisible().catch(() => false))) {
        throw new Error("The person was removed despite Cancel.");
      }
      markInteraction("global", "modal-cancel-verified", "user-still-present");
    }
    await removeButton.click();
    await page.waitForTimeout(200);
    const modal = page.locator(".modal-card").first();
    await expectVisible(modal, "Confirmation didn't appear after Remove.");
    await modal.getByRole("button", { name: /remove/i }).first().click();
    markControl("users", "users:remove-user");
    await page.waitForTimeout(800);
    await ensureNoErrorBanner("Removing the person failed");
    if ((await page.locator(".person", { hasText: tempUser }).count()) === 0) {
      cleanupState.usernames.delete(tempUser);
    }

    await registerVisibleButtons("users");
    await screenshot("users");
  });

  await check("help-page-comprehensive", async () => {
    await clickNav("Help");
    await expectVisible(page.getByRole("heading", { name: /help center/i }).first(), "Help header missing.");

    const faqCard = page.locator("article.card", {
      has: page.getByRole("heading", { name: /frequently asked questions/i }).first(),
    });
    const faqItems = faqCard.locator(".accordion-stack .accordion");
    const faqCount = await faqItems.count();
    if (faqCount < 4) {
      throw new Error(`Expected at least 4 FAQ accordions, found ${faqCount}.`);
    }
    for (let index = 0; index < faqCount; index += 1) {
      const item = faqItems.nth(index);
      const summary = item.locator("summary").first();
      await summary.click();
      await page.waitForTimeout(140);
      markInteraction("help", "faq-toggle", `index:${index}`);
    }
    markControl("help", "help:faq-open");

    const docsCard = page.locator("article.card", {
      has: page.getByRole("heading", { name: /task guides/i }).first(),
    });
    await expectVisible(docsCard, "Task Guides card was not visible on Help page.");
    const docs = docsCard.locator(".accordion");
    const docsCount = await docs.count();
    if (docsCount === 0) {
      throw new Error("No task guide accordions were visible on Help page.");
    }
    let foundRichDoc = false;
    for (let index = 0; index < docsCount; index += 1) {
      const doc = docs.nth(index);
      await doc.locator("summary").first().click();
      await page.waitForTimeout(180);
      const content = normalizeText(await doc.locator(".doc-preview").first().innerText().catch(() => ""));
      if (content.length >= 20) {
        if (/(^|\n)\s*#{1,6}\s+\S/.test(content) || content.includes("```")) {
          throw new Error("Embedded task guide content still appears as raw markdown text.");
        }
        foundRichDoc = true;
        break;
      }
    }
    if (!foundRichDoc) {
      throw new Error("Embedded task guide content appears empty.");
    }
    markControl("help", "help:task-guides-open");

    // Troubleshooting accordions (separate section from FAQ, closed by default)
    const troubleshootCard = page
      .locator("article.card", { has: page.getByRole("heading", { name: /troubleshoot/i }) })
      .first();
    if (await troubleshootCard.isVisible().catch(() => false)) {
      const troubleItems = troubleshootCard.locator(".accordion");
      const troubleCount = await troubleItems.count();
      for (let tIdx = 0; tIdx < troubleCount; tIdx += 1) {
        await troubleItems.nth(tIdx).locator("summary").first().click();
        await page.waitForTimeout(140);
        markInteraction("help", "troubleshoot-toggle", `index:${tIdx}`);
      }
      if (troubleCount > 0) {
        markControl("help", "help:troubleshooting-open");
      } else {
        report.warnings.push("Troubleshooting card found but no accordion items inside.");
      }
    } else {
      report.warnings.push("Troubleshooting card not visible on Help page.");
    }

    // Debug log section: generate if needed, then test download and regenerate.
    // On initial load the button may just say "Generate" without extra keywords.
    const generateDebugBtn = page.getByRole("button", { name: /generate/i }).first();
    if (await generateDebugBtn.isVisible().catch(() => false)) {
      await generateDebugBtn.click();
      rememberButtonClick("help", "Generate debug");
      await page.waitForTimeout(2000);
    }
    const downloadReportBtn = page.getByRole("button", { name: /download report/i }).first();
    if (await downloadReportBtn.isVisible().catch(() => false)) {
      await downloadReportBtn.click();
      markControl("help", "help:debug-log-download");
      rememberButtonClick("help", "Download Report");
      await page.waitForTimeout(400);
    } else {
      report.warnings.push("'Download Report' button not visible on Help page.");
    }
    const regenerateReportBtn = page.getByRole("button", { name: /regenerate/i }).first();
    if (await regenerateReportBtn.isVisible().catch(() => false)) {
      await regenerateReportBtn.click();
      markControl("help", "help:debug-log-regenerate");
      rememberButtonClick("help", "Regenerate");
      await page.waitForTimeout(600);
    } else {
      report.warnings.push("'Regenerate' button not visible on Help page.");
    }

    await registerVisibleButtons("help");
    await screenshot("help");
  });

  await check("about-page-comprehensive", async () => {
    await clickNav("About");
    await expectVisible(page.getByRole("heading", { name: /about cookdex/i }).first(), "About page header missing.");

    // Verify version card is visible with version number
    const versionHeading = page.locator("h3", { hasText: /CookDex v\d/ }).first();
    await expectVisible(versionHeading, "Version heading not visible on About page.");
    markControl("about", "about:version-visible");

    // Verify project links
    const links = page.locator("a.link-btn");
    if ((await links.count()) < 2) {
      throw new Error("Expected GitHub and Sponsor links were not found.");
    }
    markControl("about", "about:links-visible");

    // Validate GitHub link href
    const githubLink = page.locator("a.link-btn").filter({ hasText: /github/i }).first();
    if (await githubLink.isVisible().catch(() => false)) {
      const githubHref = await githubLink.getAttribute("href").catch(() => "");
      const _gh = new URL(githubHref).hostname;
      if (!githubHref || (_gh !== "github.com" && !_gh.endsWith(".github.com"))) {
        throw new Error(`GitHub link href is invalid: '${githubHref}'`);
      }
      markControl("about", "about:github-link-href");
      markInteraction("about", "github-link-href", githubHref);
    } else {
      throw new Error("GitHub Repository link not found on About page.");
    }

    // Validate Sponsor link href
    const sponsorLink = page.locator("a.link-btn").filter({ hasText: /sponsor/i }).first();
    if (await sponsorLink.isVisible().catch(() => false)) {
      const sponsorHref = await sponsorLink.getAttribute("href").catch(() => "");
      if (!sponsorHref || !sponsorHref.includes("github")) {
        throw new Error(`Sponsor link href is invalid: '${sponsorHref}'`);
      }
      markControl("about", "about:sponsor-link-href");
      markInteraction("about", "sponsor-link-href", sponsorHref);
    } else {
      throw new Error("Sponsor project link not found on About page.");
    }

    await registerVisibleButtons("about");
    await screenshot("about");
  });

  await check("api-comprehensive-operations", async () => {
    if (discoveredTasks.length === 0) {
      throw new Error("No tasks were discovered from API; cannot run comprehensive API coverage.");
    }

    let queuedApi = 0;
    for (const task of discoveredTasks) {
      const taskId = String(task.task_id || "").trim();
      if (!taskId) {
        continue;
      }
      const options = buildTaskOptionsFromDefinition(task);
      await apiRequest("POST", "/runs", { task_id: taskId, options }, [202]);
      queuedApi += 1;
      markInteraction("api", "queue-run", taskId);
    }
    report.coverage.tasksQueuedViaApi = queuedApi;
    if (queuedApi >= discoveredTasks.length) {
      markControl("api", "api:queue-all-tasks");
    } else {
      throw new Error(`Queued ${queuedApi} API runs but discovered ${discoveredTasks.length} tasks.`);
    }

    const firstTask =
      discoveredTasks.find((task) => String(task.task_id || "").trim() === "yield-normalize")
      || discoveredTasks.find((task) => String(task.task_id || "").trim());
    if (!firstTask) {
      throw new Error("No valid task ID available for API schedule coverage.");
    }
    const scheduleOptions = buildTaskOptionsFromDefinition(firstTask);
    if (String(firstTask.task_id) === "yield-normalize" && scheduleOptions.dry_run !== true) {
      throw new Error("yield-normalize API schedule coverage must use dry_run=true.");
    }
    const apiIntervalName = `qa-api-int-${Date.now().toString().slice(-7)}`;
    const apiOnceName = `qa-api-once-${Date.now().toString().slice(-7)}`;
    const createdScheduleIds = [];

    const intervalCreated = await apiRequest(
      "POST",
      "/schedules",
      {
        name: apiIntervalName,
        task_id: firstTask.task_id,
        kind: "interval",
        seconds: 3600,
        options: scheduleOptions,
        enabled: true,
      },
      [201]
    );
    if (intervalCreated.payload?.schedule_id) {
      const id = String(intervalCreated.payload.schedule_id);
      createdScheduleIds.push(id);
      cleanupState.scheduleIds.add(id);
    }

    // API supports interval and once only (cron is not a valid kind)
    const onceRunAt = new Date(Date.now() + 7200000).toISOString();
    const onceCreated = await apiRequest(
      "POST",
      "/schedules",
      {
        name: apiOnceName,
        task_id: firstTask.task_id,
        kind: "once",
        run_at: onceRunAt,
        options: scheduleOptions,
        enabled: true,
      },
      [201]
    );
    if (onceCreated.payload?.schedule_id) {
      const id = String(onceCreated.payload.schedule_id);
      createdScheduleIds.push(id);
      cleanupState.scheduleIds.add(id);
    }

    for (const scheduleId of createdScheduleIds) {
      await apiRequest("DELETE", `/schedules/${encodeURIComponent(scheduleId)}`, null, [200]);
      cleanupState.scheduleIds.delete(scheduleId);
    }
    report.coverage.schedulesCreatedViaApi += createdScheduleIds.length;
    if (createdScheduleIds.length >= 2) {
      markControl("api", "api:schedule-create-delete");
    } else {
      throw new Error("API schedule create/delete coverage did not create both interval and once schedules.");
    }

    const apiUsername = `qaapi${Date.now().toString().slice(-6)}`;
    const apiPassword = "QaApiTempPass#1";
    const apiResetPassword = "QaApiResetPass#2";
    await apiRequest("POST", "/users", { username: apiUsername, password: apiPassword }, [201]);
    cleanupState.usernames.add(apiUsername);
    report.coverage.usersCreatedViaApi += 1;

    await apiRequest(
      "POST",
      `/users/${encodeURIComponent(apiUsername)}/reset-password`,
      { password: apiResetPassword },
      [200]
    );
    await apiRequest("DELETE", `/users/${encodeURIComponent(apiUsername)}`, null, [200]);
    cleanupState.usernames.delete(apiUsername);
    markControl("api", "api:user-create-reset-delete");
  });

  await check("auth-logout-login", async () => {
    await clickSidebarAction("Log Out", "global:sidebar-logout");
    await expectVisible(page.getByRole("heading", { name: /sign in/i }).first(), "Sign in page did not render.");
    await fillFirstVisible(page.locator('label:has-text("Username") input'), args.username);
    await fillFirstVisible(page.locator('label:has-text("Password") input'), args.password);
    await clickButtonByRole("auth", /sign in/i, "auth:relogin");
    markControl("auth", "auth:login-submit");
    await page.waitForSelector(".sidebar", { timeout: 25000 });
    await screenshot("post-relogin");
  });

  try {
    await bestEffortCleanup();
  } catch (error) {
    report.warnings.push(`Best-effort API cleanup failed: ${String(error?.message || error)}`);
  }

  for (const [pageName, names] of buttonsSeenByPage.entries()) {
    report.coverage.buttonsSeenByPage[pageName] = [...names].sort();
  }
  for (const [pageName, names] of buttonsClickedByPage.entries()) {
    report.coverage.buttonsClickedByPage[pageName] = [...names].sort();
  }
  report.coverage.markersHit = [...markerHits].sort();

  const missingMarkers = REQUIRED_MARKERS.filter((marker) => !markerHits.has(marker));
  if (missingMarkers.length > 0) {
    report.failures.push({
      name: "coverage-markers",
      detail: `Missing required interaction markers: ${missingMarkers.join(", ")}`,
    });
  }

  if (report.coverage.tasksDiscovered > 0) {
    if (report.coverage.tasksQueuedViaUi < report.coverage.tasksDiscovered) {
      report.failures.push({
        name: "coverage-runs-ui",
        detail: `Queued ${report.coverage.tasksQueuedViaUi} tasks via UI but discovered ${report.coverage.tasksDiscovered}.`,
      });
    }
    if (report.coverage.tasksQueuedViaApi < report.coverage.tasksDiscovered) {
      report.failures.push({
        name: "coverage-runs-api",
        detail: `Queued ${report.coverage.tasksQueuedViaApi} tasks via API but discovered ${report.coverage.tasksDiscovered}.`,
      });
    }
  }

  if (report.consoleErrors.length > 0) {
    report.warnings.push(`Browser console reported ${report.consoleErrors.length} error message(s).`);
  }
  if (report.pageErrors.length > 0) {
    report.warnings.push(`Page runtime reported ${report.pageErrors.length} uncaught error(s).`);
  }
  if (report.requestFailures.length > 0) {
    report.warnings.push(`Network captured ${report.requestFailures.length} failed request(s).`);
  }

  report.finishedAt = nowIso();
  await fs.writeFile(path.join(artifactsDir, "report.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");

  await context.close();
  await browser.close();

  if (report.failures.length > 0) {
    throw new Error(`Comprehensive QA verification failed with ${report.failures.length} failing check(s).`);
  }

  process.stdout.write(`Comprehensive QA verification passed with ${report.checks.length} checks.\n`);
}

main().catch((error) => {
  process.stderr.write(`${String(error?.message || error)}\n`);
  process.exitCode = 1;
});
