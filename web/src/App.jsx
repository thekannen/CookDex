import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "wouter";
import wordmark from "./assets/CookDex_wordmark.webp";
import emblem from "./assets/CookDex_light.webp";

import { BASE_PATH, NAV_ITEMS, PAGE_META, CONFIG_LABELS, TAXONOMY_FILE_NAMES } from "./constants";
import {
  api,
  moveArrayItem,
  normalizeCookbookEntries,
  normalizeErrorMessage,
  normalizeLabelEntries,
  normalizeToolEntries,
  normalizeUnitEntries,
  parseAliasInput,
  parseQueryFilter,
  buildQueryFilter,
  FILTER_FIELDS,
  FILTER_OPERATORS,
  parseLineEditorContent,
  isOwnerRole,
  userRoleLabel,
} from "./utils.jsx";
import Icon from "./components/Icon";
import RecipeWorkspacePage from "./pages/recipe-workspace/RecipeWorkspacePage";
import UpdateNotice from "./components/UpdateNotice.jsx";
import AboutPage from "./pages/about/AboutPage";
import HelpPage from "./pages/help/HelpPage";
import UsersPage from "./pages/users/UsersPage";
import DiscoverPage from "./features/discover/DiscoverPage";
import AutomationsPage from "./features/automations/AutomationsPage";
import SettingsPage from "./pages/settings/SettingsPage";
import LibraryPage from "./features/library/LibraryPage";
import OrganizePage from "./features/organize/OrganizePage";
import TasksPage from "./pages/tasks/TasksPage";
import WelcomeWizard, { dismissWelcome, welcomeDismissed } from "./features/welcome/WelcomeWizard";

const HOME_PAGE = "library";
// Old bookmarks keep working.
const PAGE_ALIASES = { overview: HOME_PAGE, "recipe-sources": "discover" };
// Pages that became tabs of another page.
const ROUTE_REDIRECTS = { users: "/settings/people", about: "/help/about" };

function pageIdFromLocation(location) {
  const segment = String(location || "/").replace(/^\/+/, "").split("/")[0] || HOME_PAGE;
  const pageId = PAGE_ALIASES[segment] || segment;
  return NAV_ITEMS.some((item) => item.id === pageId) ? pageId : HOME_PAGE;
}

function canAccessNavItem(item, role) {
  return !item.ownerOnly || isOwnerRole(role);
}

function sanitizeCachedDataForRole(data, role) {
  if (!data || typeof data !== "object" || isOwnerRole(role)) {
    return data;
  }
  return {
    ...data,
    users: { items: [] },
    settings: null,
  };
}

export default function App() {
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(null); // { text, tone }

  const [setupRequired, setSetupRequired] = useState(false);
  const [registerUsername, setRegisterUsername] = useState("admin");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerPasswordConfirm, setRegisterPasswordConfirm] = useState("");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [session, setSession] = useState(null);
  const sessionRef = useRef(null);

  const [theme, setTheme] = useState(() => {
    const stored = window.localStorage.getItem("cookdex_webui_theme");
    if (stored === "light" || stored === "dark") {
      return stored;
    }
    return "light";
  });

  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem("cookdex_sidebar") === "collapsed");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  // The URL is the only source of truth for the current page. wouter's
  // <Router base> (see main.jsx) strips the base path, so "/" is home.
  const [location, setLocation] = useLocation();
  const activePage = pageIdFromLocation(location);
  const subPage = String(location || "/").replace(/^\/+/, "").split("/")[1] || "";

  useEffect(() => {
    const segment = String(location || "/").replace(/^\/+/, "").split("/")[0];
    if (ROUTE_REDIRECTS[segment]) setLocation(ROUTE_REDIRECTS[segment], { replace: true });
  }, [location]);

  const [tasks, setTasks] = useState([]);
  const [runs, setRuns] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [users, setUsers] = useState([]);

  const [configFiles, setConfigFiles] = useState([]);
  const [activeConfig, setActiveConfig] = useState("categories");
  const [activeConfigBody, setActiveConfigBody] = useState("[]\n");
  const [activeConfigMode, setActiveConfigMode] = useState("line-pills");
  const [activeConfigListKind, setActiveConfigListKind] = useState("name_object");
  const [activeConfigItems, setActiveConfigItems] = useState([]);
  const [activeCookbookItems, setActiveCookbookItems] = useState([]);
  const [activeToolItems, setActiveToolItems] = useState([]);
  const [activeLabelItems, setActiveLabelItems] = useState([]);
  const [activeUnitItems, setActiveUnitItems] = useState([]);
  const [toolDraft, setToolDraft] = useState({ name: "", onHand: false });
  const [labelDraft, setLabelDraft] = useState({ name: "", color: "#959595" });
  const [unitDraft, setUnitDraft] = useState({ name: "", pluralName: "", abbreviation: "", pluralAbbreviation: "", description: "", fraction: true, useAbbreviation: false, aliases: [] });
  const [configDraftItem, setConfigDraftItem] = useState("");
  const [cookbookDraft, setCookbookDraft] = useState({
    name: "",
    description: "",
    queryFilterString: "",
    filterRows: [],
    public: false,
    position: 1,
  });
  const [dragIndex, setDragIndex] = useState(null);

  const [taxonomyBootstrapMode, setTaxonomyBootstrapMode] = useState("replace");
  const [starterPackMode, setStarterPackMode] = useState("merge");
  const [taxonomyActionLoading, setTaxonomyActionLoading] = useState("");
  const [taxonomySetupFiles, setTaxonomySetupFiles] = useState([...TAXONOMY_FILE_NAMES]);

  const [confirmModal, setConfirmModal] = useState(null);
  const [forcedResetPending, setForcedResetPending] = useState(false);
  const [forcedResetPassword, setForcedResetPassword] = useState("");
  const [forcedResetShowPass, setForcedResetShowPass] = useState(false);

  const [taxonomyItemsByFile, setTaxonomyItemsByFile] = useState({});
  const [overviewMetrics, setOverviewMetrics] = useState(null);
  const [qualityMetrics, setQualityMetrics] = useState(null);
  const [aboutMeta, setAboutMeta] = useState(null);
  const [healthMeta, setHealthMeta] = useState(null);
  const [lastLoadedAt, setLastLoadedAt] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [taskHandoff, setTaskHandoff] = useState(null);
  const [showWelcome, setShowWelcome] = useState(false);

  const openConfigRequestRef = useRef(0);

  const taskTitleById = useMemo(() => {
    const map = new Map();
    for (const task of tasks) {
      map.set(task.task_id, task.title || task.task_id);
    }
    return map;
  }, [tasks]);

  const activePageMeta = PAGE_META[`${activePage}/${subPage}`] || PAGE_META[activePage] || PAGE_META.library;
  const visibleNavItems = useMemo(
    () => NAV_ITEMS.filter((item) => canAccessNavItem(item, session?.role)),
    [session]
  );



  const taxonomyCounts = useMemo(() => {
    const rows = {};
    for (const name of TAXONOMY_FILE_NAMES) {
      const content = taxonomyItemsByFile[name];
      rows[name] = Array.isArray(content) ? content.length : 0;
    }
    return rows;
  }, [taxonomyItemsByFile]);

  const availableFilterOptions = useMemo(() => {
    const extractNames = (items) => {
      if (!Array.isArray(items)) return [];
      return items
        .map((item) => (typeof item === "string" ? item : item?.name || null))
        .filter(Boolean);
    };
    return {
      categories: extractNames(taxonomyItemsByFile.categories),
      tags: extractNames(taxonomyItemsByFile.tags),
      tools: extractNames(taxonomyItemsByFile.tools),
    };
  }, [taxonomyItemsByFile]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("cookdex_webui_theme", theme);
  }, [theme]);

  useEffect(() => {
    // Each page starts at the top instead of inheriting the last scroll.
    window.scrollTo(0, 0);
  }, [activePage]);

  useEffect(() => {
    if (!session) return;
    const currentNav = NAV_ITEMS.find((item) => item.id === activePage);
    if (currentNav && !canAccessNavItem(currentNav, session.role)) {
      navigateTo(HOME_PAGE);
    }
  }, [activePage, session]);

  function navigateTo(pageId) {
    if (ROUTE_REDIRECTS[pageId]) {
      setLocation(ROUTE_REDIRECTS[pageId]);
      return;
    }
    setLocation(pageId === HOME_PAGE ? "/" : `/${pageId}`);
  }

  useEffect(() => {
    window.localStorage.setItem("cookdex_sidebar", sidebarCollapsed ? "collapsed" : "expanded");
  }, [sidebarCollapsed]);

  // Lazy-load taxonomy content only when navigating to pages that need it.
  const taxonomyLoaded = React.useRef(false);
  useEffect(() => {
    if (!session) return;
    if (activePage === "recipe-organization" || (activePage === "settings" && isOwnerRole(session.role))) {
      if (!taxonomyLoaded.current) {
        taxonomyLoaded.current = true;
        loadTaxonomyContent();
      }
    }
  }, [activePage, session]);

  const bannerTimer = React.useRef(null);

  function clearBanners() {
    setError("");
    setNotice(null);
    clearTimeout(bannerTimer.current);
  }

  // showNotice(text) confirms something finished (success). Pass
  // { tone: "info" | "warning" } for progress or nothing-to-do messages, and
  // { duration } in ms to change how long it stays. A number still works as
  // the duration.
  function showNotice(msg, options = {}) {
    const opts = typeof options === "number" ? { duration: options } : options || {};
    const tone = opts.tone || "success";
    clearTimeout(bannerTimer.current);
    if (!msg) {
      setNotice(null);
      return;
    }
    setNotice({ text: msg, tone });
    bannerTimer.current = setTimeout(() => { setNotice(null); }, opts.duration ?? (tone === "warning" ? 9000 : 5000));
  }

  function handleError(exc) {
    setNotice(null);
    clearTimeout(bannerTimer.current);
    setError(normalizeErrorMessage(exc?.message || exc));
  }

  function formatRuleSyncNotice(ruleSync, { quietIfUnchanged = true } = {}) {
    if (!ruleSync || typeof ruleSync !== "object") return "";
    const updated = Boolean(ruleSync.updated);
    if (!updated && quietIfUnchanged) return "";
    const removed = Number(ruleSync.removed_total || 0);
    const generated = Number(ruleSync.generated_total || 0);
    const canonicalized = Number(ruleSync.canonicalized_total || 0);
    const parts = [];
    if (generated > 0) parts.push(`generated ${generated} default rule${generated === 1 ? "" : "s"}`);
    if (removed > 0) parts.push(`removed ${removed} stale rule${removed === 1 ? "" : "s"}`);
    if (canonicalized > 0) {
      parts.push(`normalized ${canonicalized} target name${canonicalized === 1 ? "" : "s"}`);
    }
    if (parts.length > 0) {
      return `Tag rules synchronized: ${parts.join(", ")}.`;
    }
    if (Boolean(ruleSync.created)) return "Tag rules file initialized and synchronized.";
    return "Tag rules synchronized.";
  }

  function setConfigEditorState(content, configName = activeConfig) {
    const editor = parseLineEditorContent(content, configName);
    setActiveConfigMode(editor.mode);
    setActiveConfigListKind(editor.listKind);
    setActiveConfigItems(editor.mode === "line-pills" ? editor.items : []);
    setActiveCookbookItems(
      editor.mode === "cookbook-cards"
        ? editor.items.map((item) => ({
            ...item,
            filterRows: parseQueryFilter(item.queryFilterString),
          }))
        : []
    );
    setActiveToolItems(editor.mode === "tool-cards" ? editor.items : []);
    setActiveLabelItems(editor.mode === "label-cards" ? editor.items : []);
    setActiveUnitItems(editor.mode === "unit-cards" ? editor.items : []);
    setConfigDraftItem("");
    setCookbookDraft({
      name: "",
      description: "",
      queryFilterString: "",
      filterRows: [],
      public: false,
      position: Math.max(1, (editor.mode === "cookbook-cards" ? editor.items.length : 0) + 1),
    });
    setDragIndex(null);
    setActiveConfigBody(`${JSON.stringify(content, null, 2)}\n`);
  }

  async function refreshSession() {
    try {
      const payload = await api("/auth/session", { method: "GET" });
      sessionRef.current = payload;
      setSession(payload);
      setError("");
      if (!isOwnerRole(payload.role)) {
        patchCachedData((cached) => sanitizeCachedDataForRole(cached, payload.role));
      }
      if (payload.force_reset) setForcedResetPending(true);
      return payload;
    } catch {
      sessionRef.current = null;
      setSession(null);
      return null;
    }
  }

  async function loadTaxonomyContent() {
    const responses = await Promise.all(
      TAXONOMY_FILE_NAMES.map((name) => api(`/config/files/${name}`).catch(() => null))
    );

    const next = {};
    for (const payload of responses) {
      if (!payload || !payload.name) {
        continue;
      }
      next[payload.name] = payload.content;
    }
    setTaxonomyItemsByFile(next);

    if (activeConfig && next[activeConfig]) {
      setConfigEditorState(next[activeConfig], activeConfig);
    } else if (!activeConfig && next.categories) {
      setActiveConfig("categories");
      setConfigEditorState(next.categories, "categories");
    }
  }

  const CACHE_KEY = "cookdex_data_cache";
  const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
  const staleTimer = React.useRef(null);
  const overviewMetricsLoadingRef = React.useRef(false);

  function hasDataKey(data, key) {
    return Object.prototype.hasOwnProperty.call(data || {}, key);
  }

  function saveCachedData(partial, currentSession, { merge = false } = {}) {
    try {
      let existing = {};
      if (merge) {
        const raw = sessionStorage.getItem(CACHE_KEY);
        existing = raw ? JSON.parse(raw) : {};
      }
      const next = sanitizeCachedDataForRole(
        {
          ...existing,
          ...partial,
          savedAt: partial.savedAt || Date.now(),
          timestamp: partial.timestamp || existing.timestamp || new Date().toISOString(),
        },
        currentSession?.role
      );
      sessionStorage.setItem(CACHE_KEY, JSON.stringify(next));
      return next;
    } catch (e) {
      console.warn("sessionStorage unavailable:", e);
      return null;
    }
  }

  function clearCachedData() {
    try {
      sessionStorage.removeItem(CACHE_KEY);
    } catch (e) {
      console.warn("sessionStorage unavailable:", e);
    }
  }

  function patchCachedData(mutator) {
    try {
      const raw = sessionStorage.getItem(CACHE_KEY);
      if (!raw) return;
      const cached = JSON.parse(raw);
      const next = mutator(cached);
      if (!next || typeof next !== "object") return;
      // Keep the snapshot's original save time. A partial patch (such as a
      // metrics refresh) must not extend the TTL of everything else cached.
      next.savedAt = cached.savedAt || Date.now();
      if (!next.timestamp) {
        next.timestamp = new Date().toISOString();
      }
      sessionStorage.setItem(CACHE_KEY, JSON.stringify(next));
    } catch (e) {
      console.warn("sessionStorage unavailable:", e);
    }
  }

  function applyData(data) {
    if (hasDataKey(data, "tasks")) {
      setTasks(data.tasks?.items || []);
    }
    if (hasDataKey(data, "runs")) {
      setRuns(data.runs?.items || []);
    }
    if (hasDataKey(data, "schedules")) {
      setSchedules(data.schedules?.items || []);
    }
    if (hasDataKey(data, "config")) {
      setConfigFiles(data.config?.items || []);
    }
    if (hasDataKey(data, "users")) {
      setUsers(data.users?.items || []);
    }
    if (hasDataKey(data, "metrics")) {
      setOverviewMetrics(data.metrics);
    }
    if (hasDataKey(data, "quality")) {
      setQualityMetrics(data.quality);
    }
    if (hasDataKey(data, "about")) {
      setAboutMeta(data.about);
    }
    if (hasDataKey(data, "health")) {
      setHealthMeta(data.health);
    }
    if (hasDataKey(data, "timestamp")) {
      setLastLoadedAt(data.timestamp);
    }
  }

  function scheduleAutoRefresh() {
    clearTimeout(staleTimer.current);
    staleTimer.current = setTimeout(() => { loadData(); }, CACHE_TTL);
  }

  // Owners without a Mealie connection get the first-run wizard, unless
  // they skipped it before.
  function promptWelcomeIfUnconfigured(settingsPayload, role) {
    if (!isOwnerRole(role) || !settingsPayload?.env || welcomeDismissed()) return;
    const env = settingsPayload.env;
    const configured = Boolean(env.MEALIE_URL?.has_value) && Boolean(env.MEALIE_API_KEY?.has_value);
    if (!configured) setShowWelcome(true);
  }

  function finishWelcome({ openTasks = false } = {}) {
    dismissWelcome();
    setShowWelcome(false);
    clearCachedData();
    loadData();
    navigateTo(openTasks ? "tasks" : HOME_PAGE);
  }

  function loadCachedData(currentSession) {
    try {
      const raw = sessionStorage.getItem(CACHE_KEY);
      if (!raw) return false;
      const cached = sanitizeCachedDataForRole(JSON.parse(raw), currentSession?.role);
      if (Date.now() - cached.savedAt > CACHE_TTL) return false;
      applyData(cached);
      promptWelcomeIfUnconfigured(cached.settings, currentSession?.role);
      scheduleAutoRefresh();
      return true;
    } catch { return false; }
  }

  const prevRunsRef = React.useRef([]);

  // Until runs report structured results, say at least whether anything was
  // written, so a preview is never mistaken for an applied change.
  function runFinishedMessage(run) {
    const title = taskTitleById.get(run.task_id) || run.task_id;
    const options = run.options || {};
    const wrote = options.dry_run === false || options.apply_cleanups === true;
    if (wrote) {
      return `${title} finished and applied its changes to Mealie.`;
    }
    if ("dry_run" in options) {
      return `${title} preview is ready. Nothing in Mealie changed. Open its output to review what would change.`;
    }
    return `${title} finished.`;
  }

  async function refreshRuns() {
    try {
      const payload = await api("/runs");
      const nextRuns = payload?.items || [];
      const prev = prevRunsRef.current;
      const qualityJustFinished = nextRuns.some((run) => {
        if (run.task_id !== "health-check") return false;
        if (run.status !== "succeeded") return false;
        const old = prev.find((r) => r.run_id === run.run_id);
        return !old || old.status !== "succeeded";
      });
      // Detect run status transitions for success/failure micro-feedback.
      if (prev.length > 0) {
        for (const run of nextRuns) {
          const old = prev.find((r) => r.run_id === run.run_id);
          if (old && old.status === "running" && run.status === "succeeded") {
            showNotice(runFinishedMessage(run), { tone: run.options?.dry_run === false ? "success" : "info" });
          } else if (old && old.status === "running" && run.status === "failed") {
            const title = taskTitleById.get(run.task_id) || run.task_id;
            showNotice(`${title} failed. Open its output on the Tasks page to see why.`, { tone: "warning" });
          }
        }
      }
      prevRunsRef.current = nextRuns;
      setRuns(nextRuns);
      if (qualityJustFinished) {
        api("/metrics/quality").then((q) => setQualityMetrics(q)).catch(() => {});
      }
    } catch (exc) { handleError(exc); }
  }

  async function refreshSchedules() {
    try {
      const payload = await api("/schedules");
      const nextSchedules = payload?.items || [];
      setSchedules(nextSchedules);
      patchCachedData((cached) => ({ ...cached, schedules: { items: nextSchedules } }));
    } catch (exc) { handleError(exc); }
  }

  async function refreshUsers() {
    if (!isOwnerRole(session?.role)) {
      setUsers([]);
      return;
    }
    try {
      const payload = await api("/users");
      setUsers(payload?.items || []);
    } catch (exc) { handleError(exc); }
  }

  async function refreshTasks() {
    try {
      const payload = await api("/tasks");
      setTasks(payload?.items || []);
    } catch (exc) { handleError(exc); }
  }

  // Default to the ref, not the `session` state: timers and callbacks can run
  // with a closure from before sign-in finished, when `session` was null.
  async function refreshOverviewMetrics(currentSession = sessionRef.current) {
    if (!currentSession || currentSession.force_reset || overviewMetricsLoadingRef.current) {
      return;
    }
    overviewMetricsLoadingRef.current = true;
    try {
      const metricsPayload = await api("/metrics/overview").catch(() => null);
      const activeSession = sessionRef.current;
      if (
        !activeSession ||
        activeSession.force_reset ||
        activeSession.username !== currentSession.username
      ) {
        return;
      }
      setOverviewMetrics(metricsPayload);
      patchCachedData((cached) =>
        sanitizeCachedDataForRole({ ...cached, metrics: metricsPayload }, currentSession?.role)
      );
    } catch {
      // Live Mealie metrics are useful on the overview page, but they should not
      // block local task and activity data from loading.
    } finally {
      overviewMetricsLoadingRef.current = false;
    }
  }

  async function loadData(currentSession = sessionRef.current) {
    if (isLoading || !currentSession) return;
    setIsLoading(true);
    try {
      const isOwner = isOwnerRole(currentSession?.role);
      const [
        taskPayload, runPayload, schedulePayload, settingsPayload,
        configPayload, usersPayload,
        qualityPayload, aboutPayload, healthPayload,
      ] = await Promise.all([
        api("/tasks"),
        api("/runs"),
        api("/schedules"),
        isOwner ? api("/settings") : Promise.resolve(null),
        api("/config/files"),
        isOwner ? api("/users") : Promise.resolve({ items: [] }),
        api("/metrics/quality").catch(() => null),
        api("/about/meta").catch(() => null),
        api("/health").catch(() => null),
      ]);

      const data = sanitizeCachedDataForRole({
        tasks: taskPayload, runs: runPayload, schedules: schedulePayload,
        settings: settingsPayload, config: configPayload, users: usersPayload,
        quality: qualityPayload,
        about: aboutPayload, health: healthPayload,
        timestamp: new Date().toISOString(), savedAt: Date.now(),
      }, currentSession?.role);

      applyData(data);
      promptWelcomeIfUnconfigured(settingsPayload, currentSession?.role);

      saveCachedData(data, currentSession, { merge: true });

      clearBanners();
      scheduleAutoRefresh();
      refreshOverviewMetrics(currentSession);
    } catch (exc) {
      handleError(exc);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      try {
        const payload = await api("/auth/bootstrap-status");
        if (!active) {
          return;
        }

        const required = Boolean(payload.setup_required);
        setSetupRequired(required);
        if (required) {
          setSession(null);
          return;
        }

        const nextSession = await refreshSession();
        if (nextSession) {
          if (nextSession.force_reset) {
            return;
          }
          if (!loadCachedData(nextSession)) {
            await loadData(nextSession);
          } else {
            refreshOverviewMetrics(nextSession);
          }
        }
      } catch (exc) {
        if (active) {
          handleError(exc);
        }
      }
    }

    bootstrap();
    return () => {
      active = false;
    };
  }, []);

  async function registerFirstUser(event) {
    event.preventDefault();
    try {
      clearBanners();
      if (registerPassword !== registerPasswordConfirm) {
        setError("Passwords do not match.");
        return;
      }
      await api("/auth/register", {
        method: "POST",
        body: {
          username: registerUsername,
          password: registerPassword,
        },
      });
      setRegisterPassword("");
      setRegisterPasswordConfirm("");
      setSetupRequired(false);
      clearCachedData();
      const nextSession = await refreshSession();
      setShowWelcome(true);
      await loadData(nextSession);
    } catch (exc) {
      handleError(exc);
    }
  }

  async function doLogin(event) {
    event.preventDefault();
    try {
      clearBanners();
      const loginResult = await api("/auth/login", { method: "POST", body: { username, password } });
      setPassword("");
      clearCachedData();
      const nextSession = await refreshSession();
      if (loginResult?.force_reset) {
        setForcedResetPending(true);
      } else {
        await loadData(nextSession);
        showNotice("Signed in successfully.");
      }
    } catch (exc) {
      handleError(exc);
    }
  }

  async function doLogout() {
    try {
      clearBanners();
      await api("/auth/logout", { method: "POST" });
      sessionRef.current = null;
      setSession(null);
      setRuns([]);
      setSchedules([]);
      setUsers([]);
      clearCachedData();
    } catch (exc) {
      handleError(exc);
    }
  }

  function configDraftValue(index, value) {
    setActiveConfigItems((prev) => prev.map((item, rowIndex) => (rowIndex === index ? value : item)));
  }

  function addConfigLine() {
    const value = configDraftItem.trim();
    if (!value) {
      return;
    }
    setActiveConfigItems((prev) => [...prev, value]);
    setConfigDraftItem("");
  }

  function removeConfigLine(index) {
    setActiveConfigItems((prev) => prev.filter((_, rowIndex) => rowIndex !== index));
  }

  function moveConfigLine(fromIndex, toIndex) {
    setActiveConfigItems((prev) => moveArrayItem(prev, fromIndex, toIndex));
  }

  function updateCookbookEntry(index, key, value) {
    setActiveCookbookItems((prev) =>
      prev.map((item, rowIndex) => (rowIndex === index ? { ...item, [key]: value } : item))
    );
  }

  function addCookbookEntry() {
    const name = String(cookbookDraft.name || "").trim();
    if (!name) {
      return;
    }
    const parsedPosition = Number.parseInt(String(cookbookDraft.position || ""), 10);
    const nextPosition = Number.isFinite(parsedPosition) && parsedPosition > 0 ? parsedPosition + 1 : 1;
    setActiveCookbookItems((prev) => [
      ...prev,
      {
        name,
        description: String(cookbookDraft.description || "").trim(),
        queryFilterString: cookbookDraft.queryFilterString,
        filterRows: [...(cookbookDraft.filterRows || [])],
        public: Boolean(cookbookDraft.public),
        position: Number.isFinite(parsedPosition) && parsedPosition > 0 ? parsedPosition : prev.length + 1,
      },
    ]);
    setCookbookDraft((prev) => ({
      ...prev,
      name: "",
      description: "",
      queryFilterString: "",
      filterRows: [],
      public: false,
      position: nextPosition,
    }));
  }

  function updateCookbookFilterRows(index, newRows) {
    setActiveCookbookItems((prev) =>
      prev.map((item, i) =>
        i === index
          ? { ...item, filterRows: newRows, queryFilterString: buildQueryFilter(newRows) }
          : item
      )
    );
  }

  function removeCookbookEntry(index) {
    setActiveCookbookItems((prev) => prev.filter((_, rowIndex) => rowIndex !== index));
  }

  function moveCookbookEntry(fromIndex, toIndex) {
    setActiveCookbookItems((prev) => moveArrayItem(prev, fromIndex, toIndex));
  }

  // --- Tool card helpers ---
  function addToolEntry() {
    if (!toolDraft.name.trim()) return;
    setActiveToolItems((prev) => [...prev, { ...toolDraft, name: toolDraft.name.trim() }]);
    setToolDraft({ name: "", onHand: false });
  }
  function updateToolEntry(index, key, value) {
    setActiveToolItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [key]: value } : item))
    );
  }
  function removeToolEntry(index) {
    setActiveToolItems((prev) => prev.filter((_, i) => i !== index));
  }
  function moveToolEntry(from, to) {
    setActiveToolItems((prev) => moveArrayItem(prev, from, to));
  }

  // --- Label card helpers ---
  function addLabelEntry() {
    if (!labelDraft.name.trim()) return;
    setActiveLabelItems((prev) => [...prev, { ...labelDraft, name: labelDraft.name.trim() }]);
    setLabelDraft({ name: "", color: "#959595" });
  }
  function updateLabelEntry(index, key, value) {
    setActiveLabelItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [key]: value } : item))
    );
  }
  function removeLabelEntry(index) {
    setActiveLabelItems((prev) => prev.filter((_, i) => i !== index));
  }
  function moveLabelEntry(from, to) {
    setActiveLabelItems((prev) => moveArrayItem(prev, from, to));
  }

  // --- Unit card helpers ---
  function addUnitEntry() {
    if (!unitDraft.name.trim()) return;
    const aliases = Array.isArray(unitDraft.aliases) ? unitDraft.aliases : parseAliasInput(unitDraft.aliases);
    setActiveUnitItems((prev) => [...prev, { ...unitDraft, name: unitDraft.name.trim(), aliases }]);
    setUnitDraft({ name: "", pluralName: "", abbreviation: "", pluralAbbreviation: "", description: "", fraction: true, useAbbreviation: false, aliases: [] });
  }
  function updateUnitEntry(index, key, value) {
    if (key === "aliases") {
      const aliases = Array.isArray(value) ? value : parseAliasInput(value);
      setActiveUnitItems((prev) =>
        prev.map((item, i) => (i === index ? { ...item, aliases } : item))
      );
      return;
    }
    setActiveUnitItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [key]: value } : item))
    );
  }
  function removeUnitEntry(index) {
    setActiveUnitItems((prev) => prev.filter((_, i) => i !== index));
  }
  function moveUnitEntry(from, to) {
    setActiveUnitItems((prev) => moveArrayItem(prev, from, to));
  }

  async function openConfig(name) {
    const requestId = openConfigRequestRef.current + 1;
    openConfigRequestRef.current = requestId;
    try {
      clearBanners();
      const payload = await api(`/config/files/${name}`);
      if (requestId !== openConfigRequestRef.current) {
        return;
      }
      setActiveConfig(name);
      setConfigEditorState(payload.content, name);
    } catch (exc) {
      if (requestId !== openConfigRequestRef.current) {
        return;
      }
      handleError(exc);
    }
  }

  async function initializeFromMealieBaseline(includeFiles = taxonomySetupFiles) {
    try {
      clearBanners();
      if (!Array.isArray(includeFiles) || includeFiles.length === 0) {
        setError("Select at least one taxonomy file.");
        return;
      }
      setTaxonomyActionLoading("mealie");
      const payload = await api("/config/taxonomy/initialize-from-mealie", {
        method: "POST",
        body: { mode: taxonomyBootstrapMode, files: includeFiles },
      });
      await loadTaxonomyContent();
      const changedCount = Object.keys(payload?.changes || {}).length;
      const ruleNote = formatRuleSyncNotice(payload?.rule_sync);
      showNotice(
        `Managed baseline initialized from Mealie (${taxonomyBootstrapMode}). Updated ${changedCount} file(s).${ruleNote ? ` ${ruleNote}` : ""}`
      );
    } catch (exc) {
      handleError(exc);
    } finally {
      setTaxonomyActionLoading("");
    }
  }

  async function importStarterPack(includeFiles = taxonomySetupFiles) {
    try {
      clearBanners();
      if (!Array.isArray(includeFiles) || includeFiles.length === 0) {
        setError("Select at least one taxonomy file.");
        return;
      }
      setTaxonomyActionLoading("starter-pack");
      const payload = await api("/config/taxonomy/import-starter-pack", {
        method: "POST",
        body: {
          mode: starterPackMode,
          files: includeFiles,
        },
      });
      await loadTaxonomyContent();
      const changedCount = Object.keys(payload?.changes || {}).length;
      const ruleNote = formatRuleSyncNotice(payload?.rule_sync);
      showNotice(
        `Starter pack imported (${starterPackMode}). Updated ${changedCount} file(s).${ruleNote ? ` ${ruleNote}` : ""}`
      );
    } catch (exc) {
      handleError(exc);
    } finally {
      setTaxonomyActionLoading("");
    }
  }

  async function doForcedReset(event) {
    event.preventDefault();
    const newPass = forcedResetPassword.trim();
    if (!newPass) {
      setError("Enter a new password.");
      return;
    }
    try {
      clearBanners();
      await api(`/users/${encodeURIComponent(session.username)}/reset-password`, {
        method: "POST",
        body: { password: newPass, force_reset: false },
      });
      const nextSession = await refreshSession();
      setForcedResetPending(false);
      setForcedResetPassword("");
      setForcedResetShowPass(false);
      await loadData(nextSession);
      showNotice("Password changed. Welcome!");
    } catch (exc) {
      handleError(exc);
    }
  }

  function renderLibraryPage() {
    const cleanupPolicy = tasks.find((task) => task.task_id === "clean-recipes")?.policy;
    return (
      <LibraryPage
        isOwner={isOwnerRole(session?.role)}
        canApplyCleanup={isOwnerRole(session?.role) || Boolean(cleanupPolicy?.allow_dangerous)}
        recentRuns={runs}
        taskTitle={(taskId) => taskTitleById.get(taskId) || taskId}
        onOpenTask={(taskId, options) => {
          if (taskId) setTaskHandoff({ task_id: taskId, options: options || null });
          navigateTo("tasks");
        }}
        onSetup={() => setShowWelcome(true)}
        onRunsChanged={refreshRuns}
        onNotice={showNotice}
        onError={handleError}
      />
    );
  }

  function renderOrganizePage() {
    const policy = tasks.find((task) => task.task_id === "organize-apply")?.policy;
    return (
      <OrganizePage
        canApply={isOwnerRole(session?.role) || Boolean(policy?.allow_dangerous)}
        onOpenTaxonomyEditor={() => navigateTo("recipe-organization")}
        onNotice={showNotice}
        onError={handleError}
      />
    );
  }

  function renderTasksPage() {
    return (
      <TasksPage
        tasks={tasks}
        runs={runs}
        schedules={schedules}
        session={session}
        taskHandoff={taskHandoff}
        onNotice={showNotice}
        onError={handleError}
        onConfirm={setConfirmModal}
        refreshRuns={refreshRuns}
        refreshSchedules={refreshSchedules}
        refreshTasks={refreshTasks}
        clearTaskHandoff={() => setTaskHandoff(null)}
        navigateTo={navigateTo}
        sidebarCollapsed={sidebarCollapsed}
      />
    );
  }


  const GROUP_ICONS = { Connection: "link", AI: "wand", "Direct DB": "database" };
  const GROUP_DESCRIPTIONS = {
    Connection: "Mealie URL and API key",
    AI: "Provider, model, and API keys for recipe categorization",
    "Direct DB": "PostgreSQL and SSH tunnel for bulk operations",
  };

  function renderSettingsPage() {
    return (
      <SettingsPage
        session={session}
        overviewMetrics={overviewMetrics}
        qualityMetrics={qualityMetrics}
        onNotice={showNotice}
        onError={handleError}
        onSettingsSaved={() => refreshOverviewMetrics()}
      />
    );
  }

  function renderAutomationsPage() {
    return (
      <AutomationsPage
        isOwner={isOwnerRole(session?.role)}
        taskTitle={(taskId) => taskTitleById.get(taskId) || taskId}
        onOpenTasks={() => navigateTo("tasks")}
        onNotice={showNotice}
        onError={handleError}
      />
    );
  }

  function renderDiscoverPage() {
    const policy = tasks.find((task) => task.task_id === "recipe-dredger")?.policy;
    return (
      <DiscoverPage
        canImport={isOwnerRole(session?.role) || Boolean(policy?.allow_dangerous)}
        onNotice={showNotice}
        onError={handleError}
      />
    );
  }

  function renderRecipeOrganizationPage() {
    return (
      <RecipeWorkspacePage
        onNotice={showNotice}
        onError={handleError}
        onOpenTasks={(taskId) => {
          setTaskHandoff({ task_id: taskId });
          navigateTo("tasks");
        }}
        taxonomyFileNames={TAXONOMY_FILE_NAMES}
        configLabels={CONFIG_LABELS}
        taxonomySetupFiles={taxonomySetupFiles}
        setTaxonomySetupFiles={setTaxonomySetupFiles}
        taxonomyBootstrapMode={taxonomyBootstrapMode}
        setTaxonomyBootstrapMode={setTaxonomyBootstrapMode}
        starterPackMode={starterPackMode}
        setStarterPackMode={setStarterPackMode}
        taxonomyActionLoading={taxonomyActionLoading}
        onInitializeFromMealie={initializeFromMealieBaseline}
        onImportStarterPack={importStarterPack}
      />
    );
  }

  function renderUsersPage() {
    return (
      <UsersPage
        users={users}
        session={session}
        onNotice={showNotice}
        onError={handleError}
        onConfirm={setConfirmModal}
        refreshUsers={refreshUsers}
      />
    );
  }

  function renderHelpPage() {
    return <HelpPage aboutMeta={aboutMeta} />;
  }

  function renderAboutPage() {
    return <AboutPage aboutMeta={aboutMeta} healthMeta={healthMeta} lastLoadedAt={lastLoadedAt} />;
  }

  function renderTabs(pageId, tabs) {
    return (
      <div className="segmented page-tabs" role="tablist" aria-label={`${PAGE_META[pageId]?.title || pageId} sections`}>
        {tabs.map((tab) => (
          <button
            key={tab.id || "main"}
            type="button"
            role="tab"
            aria-selected={subPage === tab.id}
            className={subPage === tab.id ? "active" : ""}
            onClick={() => setLocation(tab.id ? `/${pageId}/${tab.id}` : `/${pageId}`)}
          >
            {tab.label}
          </button>
        ))}
      </div>
    );
  }

  function renderSettingsSection() {
    return (
      <>
        {renderTabs("settings", [{ id: "", label: "Settings" }, { id: "people", label: "People" }])}
        {subPage === "people" ? renderUsersPage() : renderSettingsPage()}
      </>
    );
  }

  function renderHelpSection() {
    return (
      <>
        {renderTabs("help", [{ id: "", label: "Help" }, { id: "about", label: "About" }])}
        {subPage === "about" ? renderAboutPage() : renderHelpPage()}
      </>
    );
  }

  function renderPage() {
    if (activePage === "settings" && !isOwnerRole(session?.role)) return renderLibraryPage();
    if (activePage === "organize") return renderOrganizePage();
    if (activePage === "tasks") return renderTasksPage();
    if (activePage === "settings") return renderSettingsSection();
    if (activePage === "discover") return renderDiscoverPage();
    if (activePage === "automations") return renderAutomationsPage();
    if (activePage === "recipe-organization") {
      return (
        <>
          <p className="library-banner legacy-note" role="note">
            <Icon name="info" />
            <span>
              This editor works on CookDex's own copy of your taxonomy. For tags, categories and tools, use{" "}
              <button type="button" className="link-inline" onClick={() => navigateTo("organize")}>Organize</button>
              , which changes Mealie directly. Cookbooks and labels are there now too; units are next.
            </span>
          </p>
          {renderRecipeOrganizationPage()}
        </>
      );
    }
    if (activePage === "help") return renderHelpSection();
    return renderLibraryPage();
  }

  if (setupRequired && !session) {
    return (
      <main className="auth-shell">
        <section className="auth-left">
          <img src={wordmark} alt="CookDex" className="auth-wordmark" />
          <p className="auth-badge">First-time setup made simple</p>
          <h1>Manage recipe automation without the CLI.</h1>
          <p>
            CookDex guides setup, keeps labels human-friendly, and protects secrets by default.
          </p>
          <div className="auth-points">
            <p>One owner account unlocks the full workspace.</p>
            <p>Runtime settings are grouped with plain descriptions.</p>
            <p>No recipe data changes happen until you explicitly run tasks.</p>
          </div>
        </section>

        <section className="auth-card">
          <h2>Create Owner Account</h2>
          <p>This account can manage users, schedules, settings, and runs.</p>
          <form onSubmit={registerFirstUser}>
            <label className="field">
              <span>Owner Username</span>
              <input
                value={registerUsername}
                onChange={(event) => setRegisterUsername(event.target.value)}
                placeholder="admin"
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={registerPassword}
                onChange={(event) => setRegisterPassword(event.target.value)}
                placeholder="At least 8 characters"
              />
            </label>
            <label className="field">
              <span>Confirm Password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={registerPasswordConfirm}
                onChange={(event) => setRegisterPasswordConfirm(event.target.value)}
                placeholder="Re-enter password"
              />
            </label>
            <button type="submit" className="primary">
              <Icon name="users" />
              Create Owner Account
            </button>
          </form>
          {error ? <div className="banner error">{error}</div> : null}
          <p className="muted tiny">Already set up? Reload the page after creating your account to sign in.</p>
        </section>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="auth-shell">
        <section className="auth-left">
          <img src={wordmark} alt="CookDex" className="auth-wordmark" />
          <p className="auth-badge">Welcome back</p>
          <h1>Sign in to your CookDex workspace.</h1>
          <p>CookDex guides setup, keeps labels human-friendly, and protects secrets by default.</p>
          <div className="auth-points">
            <p>Run tasks manually or on a schedule from one interface.</p>
            <p>Manage taxonomy files, categories, and cookbooks visually.</p>
            <p>Review run history and logs without touching the command line.</p>
          </div>
        </section>

        <section className="auth-card">
          <h2>Sign In</h2>
          <p>Use your CookDex user credentials.</p>
          <form onSubmit={doLogin}>
            <label className="field">
              <span>Username</span>
              <input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} />
            </label>
            <label className="field">
              <span>Password</span>
              <input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            <button type="submit" className="primary">
              <Icon name="play" />
              Sign In
            </button>
          </form>
          {error ? <div className="banner error">{error}</div> : null}
        </section>
      </main>
    );
  }

  // Pages built in features/ render their own header.
  const showPageHeader = ![HOME_PAGE, "organize", "discover", "automations"].includes(activePage);
  const showHeaderBreadcrumb = false;
  const showHeaderRefresh = false;

  return (
    <main className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <div className="mobile-header">
        <button className="icon-btn" onClick={() => setMobileSidebarOpen(true)} aria-label="Open menu">
          <Icon name="menu" />
        </button>
        <img src={wordmark} alt="CookDex" className="brand-mark" />
      </div>
      {mobileSidebarOpen && <div className="mobile-sidebar-backdrop" onClick={() => setMobileSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""} ${mobileSidebarOpen ? "mobile-open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand-wrap">
            <img src={sidebarCollapsed ? emblem : wordmark} alt="CookDex" className="brand-mark" />
          </div>
          <button className="icon-btn" onClick={() => {
            if (window.innerWidth <= 760) {
              setMobileSidebarOpen((prev) => !prev);
            } else {
              setSidebarCollapsed((prev) => !prev);
            }
          }} aria-label="Toggle sidebar">
            <Icon name="menu" />
          </button>
        </div>

        <nav className="sidebar-nav" aria-label="Main">
          <p className="muted tiny">Workspace</p>
          {visibleNavItems.filter((item) => !item.hidden).map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activePage === item.id ? "active" : ""}`}
              aria-current={activePage === item.id ? "page" : undefined}
              onClick={() => { navigateTo(item.id); setMobileSidebarOpen(false); }}
              title={item.label}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <span className="avatar"><Icon name="user" /></span>
            <div>
              <p className="tiny muted">Signed in as</p>
              <strong>{session.username}</strong>
            </div>
            <span className="role-badge">{userRoleLabel(session.role)}</span>
          </div>

          <div className="sidebar-actions">
            <div className="sidebar-actions-row">
              <button className="ghost" onClick={() => loadData()} title="Refresh data" disabled={isLoading}>
                <Icon name="refresh" className={isLoading ? "spin" : ""} />
                <span>{isLoading ? "Loading\u2026" : "Refresh"}</span>
              </button>
              <button
                className="ghost"
                onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
                title="Toggle theme"
              >
                <Icon name="contrast" />
                <span>Theme</span>
              </button>
            </div>
            <div className="sidebar-actions-row">
              <button
                className={`ghost${activePage === "help" ? " active" : ""}`}
                onClick={() => { navigateTo("help"); setMobileSidebarOpen(false); }}
                title="Help and About"
              >
                <Icon name="help" />
                <span>Help</span>
              </button>
              <button className="ghost" onClick={doLogout} title="Log out">
                <Icon name="logout" />
                <span>Log Out</span>
              </button>
            </div>
          </div>
        </div>
      </aside>

      <section className="content-shell">
        {showPageHeader ? (
          <header className="page-header card">
            <div>
              {showHeaderBreadcrumb ? <p className="eyebrow">Home / {activePageMeta.title}</p> : null}
              <h2>{activePageMeta.title}</h2>
              <p className="muted">{activePageMeta.subtitle}</p>
            </div>
            {showHeaderRefresh ? (
              <button className="ghost" onClick={() => loadData()}>
                <Icon name="refresh" />
                Refresh
              </button>
            ) : null}
          </header>
        ) : null}

        <UpdateNotice status={aboutMeta?.update} />
        <div className="toast-region" aria-live="polite">
          {error ? (
            <div className="toast error" role="alert">
              <Icon name="x-circle" />
              <span>{error}</span>
              <button className="toast-close" onClick={() => setError("")} aria-label="Dismiss error"><Icon name="x" /></button>
            </div>
          ) : notice ? (
            <div className={`toast ${notice.tone}`} role="status">
              <Icon name={notice.tone === "success" ? "check-circle" : notice.tone === "warning" ? "alertTriangle" : "info"} />
              <span>{notice.text}</span>
              <button className="toast-close" onClick={clearBanners} aria-label="Dismiss notice"><Icon name="x" /></button>
            </div>
          ) : null}
        </div>

        {showWelcome && isOwnerRole(session?.role) ? (
          <WelcomeWizard
            username={session?.username}
            onConnected={() => refreshOverviewMetrics()}
            onFinish={finishWelcome}
            onError={handleError}
          />
        ) : (
          renderPage()
        )}
      </section>

      {confirmModal && (
        <div className="modal-backdrop" onClick={() => setConfirmModal(null)} onKeyDown={(e) => { if (e.key === "Escape") setConfirmModal(null); }}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby={confirmModal.title ? "confirm-modal-title" : undefined}
            onClick={(e) => e.stopPropagation()}
          >
            {confirmModal.title ? <h3 id="confirm-modal-title" className="modal-title">{confirmModal.title}</h3> : null}
            <p>{confirmModal.message}</p>
            {Array.isArray(confirmModal.details) && confirmModal.details.length > 0 ? (
              <ul className="modal-details">
                {confirmModal.details.map((line) => <li key={line}>{line}</li>)}
              </ul>
            ) : null}
            <div className="modal-actions">
              <button className="ghost" onClick={() => setConfirmModal(null)}>Cancel</button>
              <button
                className={`primary${confirmModal.danger === false ? "" : " danger"}`}
                onClick={() => { setConfirmModal(null); confirmModal.action(); }}
              >
                {confirmModal.confirmLabel || "Remove"}
              </button>
            </div>
          </div>
        </div>
      )}

      {forcedResetPending && (
        <div className="modal-backdrop">
          <div className="modal-card forced-reset-card" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <h3>Password Reset Required</h3>
            <p className="muted">Your password was set by an administrator. Choose a new password before continuing.</p>
            <form className="run-form" onSubmit={doForcedReset}>
              <label className="field">
                <span>New Password</span>
                <div className="password-row">
                  <input
                    type={forcedResetShowPass ? "text" : "password"}
                    autoComplete="new-password"
                    value={forcedResetPassword}
                    onChange={(e) => setForcedResetPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    autoFocus
                  />
                  <button type="button" className="ghost icon-btn" onClick={() => setForcedResetShowPass((v) => !v)} aria-label={forcedResetShowPass ? "Hide password" : "Show password"}>
                    <Icon name={forcedResetShowPass ? "eye-off" : "eye"} />
                  </button>
                </div>
              </label>
              <button type="submit" className="primary">
                <Icon name="lock" />
                Set New Password
              </button>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
