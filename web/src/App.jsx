import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "wouter";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import wordmark from "./assets/CookDex_wordmark.webp";
import emblem from "./assets/CookDex_light.webp";

import { NAV_ITEMS, PAGE_META } from "./constants";
import { api, normalizeErrorMessage, isOwnerRole, userRoleLabel } from "./utils.jsx";
import Icon from "./components/Icon";
import UpdateNotice from "./components/UpdateNotice.jsx";
import MealieStatus from "./components/MealieStatus";
import { JOBS } from "./features/tools/catalog.mjs";
import LibraryPage from "./features/library/LibraryPage";
import WelcomeWizard, { dismissWelcome, welcomeDismissed } from "./features/welcome/WelcomeWizard";

// The Library is home and loads with the app; every other page is fetched
// the first time it's opened, which keeps the first load small.
const AboutPage = React.lazy(() => import("./pages/about/AboutPage"));
const HelpPage = React.lazy(() => import("./pages/help/HelpPage"));
const UsersPage = React.lazy(() => import("./pages/users/UsersPage"));
const DiscoverPage = React.lazy(() => import("./features/discover/DiscoverPage"));
const AutomationsPage = React.lazy(() => import("./features/automations/AutomationsPage"));
const ToolsPage = React.lazy(() => import("./features/tools/ToolsPage"));
const SettingsPage = React.lazy(() => import("./pages/settings/SettingsPage"));
const OrganizePage = React.lazy(() => import("./features/organize/OrganizePage"));
const TasksPage = React.lazy(() => import("./pages/tasks/TasksPage"));

const HOME_PAGE = "library";
// Old bookmarks keep working.
const PAGE_ALIASES = { overview: HOME_PAGE, "recipe-sources": "discover" };
// Pages that became tabs of another page.
const ROUTE_REDIRECTS = { users: "/settings/people", about: "/help/about", "recipe-organization": "/organize" };

function pageIdFromLocation(location) {
  const segment = String(location || "/").replace(/^\/+/, "").split("/")[0] || HOME_PAGE;
  const pageId = PAGE_ALIASES[segment] || segment;
  return NAV_ITEMS.some((item) => item.id === pageId) ? pageId : HOME_PAGE;
}

function canAccessNavItem(item, role) {
  return !item.ownerOnly || isOwnerRole(role);
}

// Server data the shell and older pages share. Each is a TanStack Query, so
// pages that change something invalidate its key (a run started from Tools
// invalidates ["runs"], which covers ["runs", "all"] here too).
const REFRESH_MS = 5 * 60 * 1000;
const itemsOf = (payload) => payload?.items || [];

export default function App() {
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(null); // { text, tone }

  const [setupRequired, setSetupRequired] = useState(false);
  const [registerUsername, setRegisterUsername] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerPasswordConfirm, setRegisterPasswordConfirm] = useState("");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [session, setSession] = useState(null);
  const queryClient = useQueryClient();
  const sessionRef = useRef(null);

  const [theme, setTheme] = useState(() => {
    let stored = null;
    try {
      stored = window.localStorage.getItem("cookdex_webui_theme");
    } catch {
      // Storage can be blocked; fall back to the system setting.
    }
    if (stored === "light" || stored === "dark") {
      return stored;
    }
    // Until someone picks one, follow the system setting.
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
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


  const [confirmModal, setConfirmModal] = useState(null);
  const [forcedResetPending, setForcedResetPending] = useState(false);
  const [forcedResetPassword, setForcedResetPassword] = useState("");
  const [forcedResetShowPass, setForcedResetShowPass] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [taskHandoff, setTaskHandoff] = useState(null);
  const [showWelcome, setShowWelcome] = useState(false);

  const isOwner = isOwnerRole(session?.role);
  const signedIn = Boolean(session) && !session.force_reset;
  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: () => api("/tasks"), enabled: signedIn, refetchInterval: REFRESH_MS });
  const runsQuery = useQuery({ queryKey: ["runs", "all"], queryFn: () => api("/runs"), enabled: signedIn, refetchInterval: REFRESH_MS });
  const schedulesQuery = useQuery({ queryKey: ["schedules"], queryFn: () => api("/schedules"), enabled: signedIn });
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: () => api("/users"), enabled: signedIn && isOwner });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: () => api("/settings"), enabled: signedIn && isOwner });
  // Nice to have; a failure here shouldn't show an error.
  const aboutQuery = useQuery({ queryKey: ["about-meta"], queryFn: () => api("/about/meta").catch(() => null), enabled: signedIn, staleTime: REFRESH_MS });
  const healthQuery = useQuery({ queryKey: ["health"], queryFn: () => api("/health").catch(() => null), enabled: signedIn, staleTime: REFRESH_MS });

  const tasks = useMemo(() => itemsOf(tasksQuery.data), [tasksQuery.data]);
  const runs = useMemo(() => itemsOf(runsQuery.data), [runsQuery.data]);
  const schedules = useMemo(() => itemsOf(schedulesQuery.data), [schedulesQuery.data]);
  const users = useMemo(() => (isOwner ? itemsOf(usersQuery.data) : []), [usersQuery.data, isOwner]);
  const aboutMeta = aboutQuery.data || null;
  const healthMeta = healthQuery.data || null;
  const lastLoadedAt = tasksQuery.dataUpdatedAt ? new Date(tasksQuery.dataUpdatedAt).toISOString() : "";

  const taskTitleById = useMemo(() => {
    const map = new Map();
    for (const task of tasks) {
      map.set(task.task_id, JOBS[task.task_id]?.title || task.title || task.task_id);
    }
    return map;
  }, [tasks]);

  const activePageMeta = PAGE_META[`${activePage}/${subPage}`] || PAGE_META[activePage] || PAGE_META.library;
  const visibleNavItems = useMemo(
    () => NAV_ITEMS.filter((item) => canAccessNavItem(item, session?.role)),
    [session]
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
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
    // The password-change screen handles this; it isn't an error to show.
    if (normalizeErrorMessage(exc?.message || exc) === "Password reset required.") return;
    setNotice(null);
    clearTimeout(bannerTimer.current);
    setError(normalizeErrorMessage(exc?.message || exc));
  }

  async function refreshSession() {
    try {
      const payload = await api("/auth/session", { method: "GET" });
      sessionRef.current = payload;
      setSession(payload);
      setError("");
      if (payload.force_reset) setForcedResetPending(true);
      return payload;
    } catch {
      sessionRef.current = null;
      setSession(null);
      return null;
    }
  }

  // Owners without a Mealie connection get the first-run wizard, unless
  // they skipped it before.
  function promptWelcomeIfUnconfigured(settingsPayload, role) {
    if (!isOwnerRole(role) || !settingsPayload?.env || welcomeDismissed()) return;
    const env = settingsPayload.env;
    const configured = Boolean(env.MEALIE_URL?.has_value) && Boolean(env.MEALIE_API_KEY?.has_value);
    if (!configured) setShowWelcome(true);
  }

  useEffect(() => {
    promptWelcomeIfUnconfigured(settingsQuery.data, session?.role);
  }, [settingsQuery.data]);

  function finishWelcome({ openTasks = false } = {}) {
    dismissWelcome();
    setShowWelcome(false);
    queryClient.invalidateQueries();
    navigateTo(openTasks ? "tools" : HOME_PAGE);
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

  // Say when a run that was going finishes, whichever page started it.
  useEffect(() => {
    const prev = prevRunsRef.current;
    if (prev.length > 0) {
      for (const run of runs) {
        const old = prev.find((r) => r.run_id === run.run_id);
        if (old && old.status === "running" && run.status === "succeeded") {
          showNotice(runFinishedMessage(run), { tone: run.options?.dry_run === false ? "success" : "info" });
        } else if (old && old.status === "running" && run.status === "failed") {
          const title = taskTitleById.get(run.task_id) || run.task_id;
          showNotice(`${title} failed. Open it under Recent activity in Tools to see why.`, { tone: "warning" });
        }
      }
    }
    prevRunsRef.current = runs;
  }, [runs]);

  // The shared data failing to load is worth saying; the pages show their own.
  const loadError = tasksQuery.error || runsQuery.error || schedulesQuery.error;
  useEffect(() => {
    if (loadError) handleError(loadError);
  }, [loadError]);

  const refreshRuns = () => queryClient.invalidateQueries({ queryKey: ["runs"] });
  const refreshSchedules = () => queryClient.invalidateQueries({ queryKey: ["schedules"] });
  const refreshUsers = () => queryClient.invalidateQueries({ queryKey: ["users"] });
  const refreshTasks = () => queryClient.invalidateQueries({ queryKey: ["tasks"] });

  // The sidebar's Refresh: everything on screen is fetched again.
  async function loadData() {
    if (isLoading) return;
    setIsLoading(true);
    try {
      await queryClient.invalidateQueries();
      clearBanners();
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

        // Signing in enables the data queries above.
        await refreshSession();
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
          username: registerUsername.trim() || "admin",
          password: registerPassword,
        },
      });
      setRegisterPassword("");
      setRegisterPasswordConfirm("");
      setSetupRequired(false);
      await refreshSession();
      setShowWelcome(true);
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
      queryClient.clear();
      await refreshSession();
      if (loginResult?.force_reset) {
        setForcedResetPending(true);
      } else {
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
      queryClient.clear();
    } catch (exc) {
      handleError(exc);
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
      await refreshSession();
      setForcedResetPending(false);
      setForcedResetPassword("");
      setForcedResetShowPass(false);
      // Anything loaded while the password change was pending is stale.
      queryClient.invalidateQueries();
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
        tasks={tasks}
        taskTitle={(taskId) => taskTitleById.get(taskId) || taskId}
        onNavigate={navigateTo}
        onConfirm={setConfirmModal}
        onOpenTask={(taskId, options) => {
          if (taskId) setTaskHandoff({ task_id: taskId, options: options || null });
          navigateTo("tools");
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


  function renderToolsPage() {
    return (
      <ToolsPage
        tasks={tasks}
        isOwner={isOwnerRole(session?.role)}
        taskTitle={(taskId) => taskTitleById.get(taskId) || taskId}
        handoff={taskHandoff}
        clearHandoff={() => setTaskHandoff(null)}
        onOpenClassic={() => navigateTo("tasks")}
        onOpenAutomations={() => navigateTo("automations")}
        onConfirm={setConfirmModal}
        onNotice={showNotice}
        onError={handleError}
      />
    );
  }

  function renderSettingsPage() {
    return (
      <SettingsPage
        session={session}
        onNotice={showNotice}
        onError={handleError}
        onSettingsSaved={() => {
          queryClient.invalidateQueries({ queryKey: ["settings"] });
          queryClient.invalidateQueries({ queryKey: ["provider-status"] });
        }}
      />
    );
  }

  function renderAutomationsPage() {
    return (
      <AutomationsPage
        tasks={tasks}
        isOwner={isOwnerRole(session?.role)}
        taskTitle={(taskId) => taskTitleById.get(taskId) || taskId}
        canApplyTask={(taskId) => isOwnerRole(session?.role) || Boolean(tasks.find((t) => t.task_id === taskId)?.policy?.allow_dangerous)}
        onOpenTasks={() => navigateTo("tools")}
        onConfirm={setConfirmModal}
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
    if (activePage === "tools") return renderToolsPage();
    if (activePage === "settings") return renderSettingsSection();
    if (activePage === "discover") return renderDiscoverPage();
    if (activePage === "automations") return renderAutomationsPage();
    if (activePage === "help") return renderHelpSection();
    return renderLibraryPage();
  }

  if (setupRequired && !session) {
    return (
      <main className="auth-shell">
        <section className="auth-left">
          <img src={wordmark} alt="CookDex" className="auth-wordmark" />
          <p className="auth-badge">Let's get you set up</p>
          <h1>A tidier Mealie library, without the busywork.</h1>
          <p>
            CookDex finds duplicates and pages that aren't recipes, fills in tags, categories and ingredients, brings in
            new recipes from sites you pick, and keeps it all tidy on a schedule.
          </p>
          <div className="auth-points">
            <p>Every change is shown to you first, and Mealie is backed up before anything changes.</p>
            <p>Next, you'll connect your Mealie and scan the library. It takes a couple of minutes.</p>
          </div>
        </section>

        <section className="auth-card">
          <h2>Create your account</h2>
          <p>You'll be the owner: you can change settings, add people, and approve changes CookDex makes on its own.</p>
          <form onSubmit={registerFirstUser}>
            <label className="field">
              <span>Your sign-in name</span>
              <input
                value={registerUsername}
                onChange={(event) => setRegisterUsername(event.target.value)}
                placeholder="like admin, or your name"
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
              <span>Same password again</span>
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
              Create account
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
          <h1>Sign in to CookDex.</h1>
          <p>Keeps your Mealie library tidy: clean-ups, tags and categories, new recipes, and backups.</p>
        </section>

        <section className="auth-card">
          <h2>Sign in</h2>
          <p>With your CookDex name and password. They're separate from Mealie's.</p>
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
  const showPageHeader = ![HOME_PAGE, "organize", "discover", "automations", "tools"].includes(activePage);
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
                onClick={() =>
                  setTheme((prev) => {
                    const next = prev === "dark" ? "light" : "dark";
                    try {
                      window.localStorage.setItem("cookdex_webui_theme", next);
                    } catch {
                      // Storage can be blocked; the choice still applies for this visit.
                    }
                    return next;
                  })
                }
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
        {session ? <MealieStatus isOwner={isOwnerRole(session?.role)} onOpenSettings={() => navigateTo("settings")} /> : null}
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
            onConnected={() => queryClient.invalidateQueries({ queryKey: ["provider-status"] })}
            onFinish={finishWelcome}
            onError={handleError}
          />
        ) : (
          <React.Suspense fallback={<p className="muted page-loading">Loading…</p>}>{renderPage()}</React.Suspense>
        )}
      </section>

      {/* A Radix dialog, so it stacks on top of an open sheet (run details, the
          automation builder) and can be clicked, rather than sitting behind it. */}
      <Dialog.Root open={Boolean(confirmModal)} onOpenChange={(open) => { if (!open) setConfirmModal(null); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="modal-backdrop" />
          {confirmModal ? (
            <Dialog.Content className="modal-card modal-card-floating" aria-describedby="confirm-modal-message">
              {confirmModal.title ? (
                <Dialog.Title className="modal-title">{confirmModal.title}</Dialog.Title>
              ) : (
                <Dialog.Title className="sr-only">Please confirm</Dialog.Title>
              )}
              <p id="confirm-modal-message">{confirmModal.message}</p>
              {Array.isArray(confirmModal.details) && confirmModal.details.length > 0 ? (
                <ul className="modal-details">
                  {confirmModal.details.map((line) => <li key={line}>{line}</li>)}
                </ul>
              ) : null}
              <div className="modal-actions">
                <Dialog.Close className="ghost">Cancel</Dialog.Close>
                <button
                  className={`primary${confirmModal.danger === false ? "" : " danger"}`}
                  onClick={() => { const action = confirmModal.action; setConfirmModal(null); action(); }}
                >
                  {confirmModal.confirmLabel || "Remove"}
                </button>
              </div>
            </Dialog.Content>
          ) : null}
        </Dialog.Portal>
      </Dialog.Root>

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
