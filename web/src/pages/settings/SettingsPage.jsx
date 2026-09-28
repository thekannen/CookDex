import React, { useState, useMemo, useEffect } from "react";
import Icon from "../../components/Icon";
import { api, normalizeErrorMessage } from "../../utils.jsx";
import { SECTIONS, sectionOf, sectionStatus, sourceNote } from "./sections.mjs";

const RUN_DURATION_KEY = "MAX_RUN_DURATION_SECONDS";
const DEFAULT_RUN_DURATION_SECONDS = 4 * 60 * 60;
const MAX_RUN_DURATION_SECONDS = 12 * 60 * 60;
const MAX_RUN_DURATION_MINUTES = MAX_RUN_DURATION_SECONDS / 60;

// Fields in the order people fill them in; anything unlisted sorts after, by label.
const FIELD_ORDER = [
  "MEALIE_URL", "MEALIE_API_KEY",
  "CATEGORIZER_PROVIDER", "OPENAI_API_KEY", "OPENAI_MODEL", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
  "OLLAMA_URL", "OLLAMA_MODEL",
  "MEALIE_DB_URL", "MEALIE_DB_SSH_HOST", "MEALIE_DB_SSH_USER", "MEALIE_DB_SSH_KEY",
  "UPDATE_CHECK_ENABLED", "MAX_RUN_DURATION_SECONDS",
];

// Tuning most people never change. Shown under "More" in their section.
const ADVANCED_KEYS = new Set([
  "AI_BATCH_HEARTBEAT_SECONDS", "OLLAMA_NUM_CTX", "OLLAMA_NUM_PREDICT", "OLLAMA_BATCH_SIZE",
  "OLLAMA_NUM_THREAD", "OLLAMA_REQUEST_TIMEOUT", "DREDGER_CACHE_EXPIRY_DAYS",
  "MEALIE_DB_SSH_HOST", "MEALIE_DB_SSH_USER", "MEALIE_DB_SSH_KEY",
]);

const ADVANCED_LABELS = { database: "Connect over SSH" };

// What stays in the compose file: things the container needs before CookDex starts.
const DEPLOYMENT_SETTINGS = [
  ["WEB_BIND_PORT", "Port CookDex listens on"],
  ["WEB_BASE_PATH", "Path it's served under, like /cookdex"],
  ["WEB_SSL, WEB_SSL_CERTFILE, WEB_SSL_KEYFILE", "HTTPS, or off behind a reverse proxy"],
  ["WEB_COOKIE_SECURE", "Only if sign-in cookies need forcing"],
  ["WEB_BOOTSTRAP_PASSWORD", "Create the first owner without the setup page"],
  ["MO_WEBUI_MASTER_KEY", "Your own key for encrypting saved secrets"],
];

const TECHNICAL_NAMES_KEY = "cookdex_settings_technical";
const MOVED_NOTE_KEY = "cookdex_settings_moved_note_seen";

function fieldRank(key) {
  const index = FIELD_ORDER.indexOf(key);
  return index === -1 ? FIELD_ORDER.length : index;
}

function clampNumber(value, min, max) {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

function parseRunDurationSeconds(value) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_RUN_DURATION_SECONDS;
  return Math.min(parsed, MAX_RUN_DURATION_SECONDS);
}

function runDurationParts(value) {
  const seconds = parseRunDurationSeconds(value);
  const totalMinutes = clampNumber(Math.round(seconds / 60), 1, MAX_RUN_DURATION_MINUTES);
  return {
    hours: Math.floor(totalMinutes / 60),
    minutes: totalMinutes % 60,
  };
}

function readFlag(key) {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeFlag(key, on) {
  try {
    window.localStorage.setItem(key, on ? "1" : "0");
  } catch {
    // Browser storage is a convenience here; the page works without it.
  }
}

export default function SettingsPage({ onNotice, onError, onSettingsSaved }) {
  const [envSpecs, setEnvSpecs] = useState({});
  const [envDraft, setEnvDraft] = useState({});
  const [envClear, setEnvClear] = useState({});
  const [moved, setMoved] = useState(null);
  const [movedNoteSeen, setMovedNoteSeen] = useState(() => readFlag(MOVED_NOTE_KEY));
  const [connectionChecks, setConnectionChecks] = useState({});
  const [availableModels, setAvailableModels] = useState({ openai: [], ollama: [], anthropic: [] });
  const [expandedAdvanced, setExpandedAdvanced] = useState(new Set());
  const [collapsed, setCollapsed] = useState(null);
  const [showTechnical, setShowTechnical] = useState(() => readFlag(TECHNICAL_NAMES_KEY));

  function toggleTechnical() {
    setShowTechnical((prev) => {
      writeFlag(TECHNICAL_NAMES_KEY, !prev);
      return !prev;
    });
  }

  const sections = useMemo(() => {
    const bySection = new Map(SECTIONS.map((section) => [section.id, []]));
    const items = Object.values(envSpecs || {})
      .filter((item) => !item.hidden)
      .sort((a, b) => fieldRank(String(a.key)) - fieldRank(String(b.key)) || String(a.label || a.key).localeCompare(String(b.label || b.key)));
    for (const item of items) {
      const id = sectionOf(item.group);
      if (id && bySection.has(id)) bySection.get(id).push(item);
    }
    return SECTIONS.map((section) => ({ ...section, items: bySection.get(section.id) })).filter((s) => s.items.length > 0);
  }, [envSpecs]);

  // Open what still needs doing; everything else starts folded.
  useEffect(() => {
    if (collapsed !== null || sections.length === 0) return;
    const open = new Set(["mealie"]);
    for (const section of sections) {
      if (sectionStatus(section.id, envSpecs).tone === "warn") open.add(section.id);
    }
    setCollapsed(new Set(sections.map((s) => s.id).filter((id) => !open.has(id))));
  }, [sections, envSpecs, collapsed]);

  useEffect(() => {
    loadSettings();
  }, []);

  function applyPayload(settingsPayload) {
    const nextSpecs = settingsPayload?.env || {};
    setEnvSpecs(nextSpecs);
    const nextDraft = {};
    for (const [key, item] of Object.entries(nextSpecs)) {
      nextDraft[key] = item.secret ? "" : String(item.value ?? "");
    }
    setEnvDraft(nextDraft);
    setEnvClear({});
    setMoved(settingsPayload?.moved_from_environment || null);
  }

  async function loadSettings() {
    try {
      applyPayload(await api("/settings"));
    } catch (exc) {
      onError(exc);
    }
  }

  function draftOverrideValue(key) {
    const value = String(envDraft[key] ?? "").trim();
    return value || null;
  }

  function secretDraft(key) {
    return envClear[key] ? "" : draftOverrideValue(key);
  }

  function setCheck(kind, state) {
    setConnectionChecks((prev) => ({ ...prev, [kind]: state }));
  }

  async function fetchAvailableModels(kind) {
    const body = {
      openai_api_key: secretDraft("OPENAI_API_KEY"),
      anthropic_api_key: secretDraft("ANTHROPIC_API_KEY"),
      ollama_url: draftOverrideValue("OLLAMA_URL"),
    };
    try {
      const result = await api(`/settings/models/${kind}`, { method: "POST", body });
      if (Array.isArray(result.models)) {
        setAvailableModels((prev) => ({ ...prev, [kind]: result.models }));

        // Keep the draft in step with the list so the <select> never shows
        // one model while the draft holds a stale one.
        const modelKey = { openai: "OPENAI_MODEL", anthropic: "ANTHROPIC_MODEL", ollama: "OLLAMA_MODEL" }[kind];
        if (modelKey && result.models.length > 0) {
          setEnvDraft((prev) => {
            const current = String(prev[modelKey] ?? "").trim();
            if (!current || !result.models.includes(current)) {
              return { ...prev, [modelKey]: result.models[0] };
            }
            return prev;
          });
        }
      }
    } catch (exc) {
      console.warn(`Failed to fetch ${kind} models:`, exc?.message || exc);
    }
  }

  async function runConnectionTest(kind) {
    setCheck(kind, { loading: true, ok: null, detail: "Checking…" });
    try {
      const body =
        kind === "db"
          ? {
              db_url: secretDraft("MEALIE_DB_URL"),
              ssh_host: draftOverrideValue("MEALIE_DB_SSH_HOST"),
              ssh_user: draftOverrideValue("MEALIE_DB_SSH_USER"),
              ssh_key: draftOverrideValue("MEALIE_DB_SSH_KEY"),
            }
          : {
              mealie_url: draftOverrideValue("MEALIE_URL"),
              mealie_api_key: secretDraft("MEALIE_API_KEY"),
              openai_api_key: secretDraft("OPENAI_API_KEY"),
              openai_model: draftOverrideValue("OPENAI_MODEL"),
              anthropic_api_key: secretDraft("ANTHROPIC_API_KEY"),
              anthropic_model: draftOverrideValue("ANTHROPIC_MODEL"),
              ollama_url: draftOverrideValue("OLLAMA_URL"),
              ollama_model: draftOverrideValue("OLLAMA_MODEL"),
            };
      const result = await api(`/settings/test/${kind}`, { method: "POST", body });
      setCheck(kind, {
        loading: false,
        ok: Boolean(result.ok),
        detail: String(result.detail || (result.ok ? "Connected." : "Couldn't connect.")),
      });
      if (result.ok && ["openai", "ollama", "anthropic"].includes(kind)) {
        fetchAvailableModels(kind);
      }
    } catch (exc) {
      setCheck(kind, { loading: false, ok: false, detail: normalizeErrorMessage(exc?.message || exc) });
    }
  }

  async function runDbDetect() {
    setCheck("dbDetect", { loading: true, ok: null, detail: "Looking for Mealie's database settings…" });
    try {
      const body = {
        ssh_host: draftOverrideValue("MEALIE_DB_SSH_HOST"),
        ssh_user: draftOverrideValue("MEALIE_DB_SSH_USER"),
        ssh_key: draftOverrideValue("MEALIE_DB_SSH_KEY"),
      };
      const result = await api("/settings/detect/db", { method: "POST", body });
      const found = result.ok ? result.detected?.MEALIE_DB_URL : "";
      if (found) {
        setEnvDraft((prev) => ({ ...prev, MEALIE_DB_URL: String(found) }));
        setEnvClear((prev) => ({ ...prev, MEALIE_DB_URL: false }));
      }
      setCheck("dbDetect", {
        loading: false,
        ok: Boolean(found),
        detail: String(result.detail || (found ? "Found it. Review the connection string, then save." : "Couldn't find it.")),
      });
    } catch (exc) {
      setCheck("dbDetect", { loading: false, ok: false, detail: normalizeErrorMessage(exc?.message || exc) });
    }
  }

  const pendingChanges = useMemo(() => {
    const env = {};
    for (const item of Object.values(envSpecs || {})) {
      if (item.hidden) continue;
      const key = String(item.key);
      const nextValue = String(envDraft[key] ?? "");
      if (item.secret) {
        if (envClear[key] === true) env[key] = null;
        else if (nextValue.trim() !== "") env[key] = nextValue;
        continue;
      }
      if (nextValue !== String(item.value ?? "")) env[key] = nextValue;
    }
    return env;
  }, [envSpecs, envDraft, envClear]);
  const changeCount = Object.keys(pendingChanges).length;

  async function saveSettings() {
    if (changeCount === 0) {
      onNotice("Nothing to save.", { tone: "info" });
      return;
    }
    try {
      applyPayload(await api("/settings", { method: "PUT", body: { env: pendingChanges } }));
      onSettingsSaved?.();
      onNotice("Settings saved. The next run uses them.");
    } catch (exc) {
      onError(exc);
    }
  }

  function toggleSection(id) {
    setCollapsed((prev) => {
      const next = new Set(prev || []);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAdvanced(id) {
    setExpandedAdvanced((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const configuredProvider = String(envDraft.CATEGORIZER_PROVIDER || "").trim().toLowerCase();
  const provider = ["ollama", "anthropic", "none"].includes(configuredProvider) ? configuredProvider : "chatgpt";

  function fitsProvider(key) {
    if (provider !== "chatgpt" && key.startsWith("OPENAI_")) return false;
    if (provider !== "anthropic" && key.startsWith("ANTHROPIC_")) return false;
    if (provider !== "ollama" && key.startsWith("OLLAMA_")) return false;
    return !(provider === "none" && key === "AI_BATCH_HEARTBEAT_SECONDS");
  }

  function isShown(key, sectionId) {
    return fitsProvider(key) && (!ADVANCED_KEYS.has(key) || expandedAdvanced.has(sectionId));
  }

  const CONNECTION_TESTS = {
    mealie: [{ id: "mealie", label: "Test Mealie", hint: "Checks the address and token together." }],
    ai: [
      { id: "openai", label: "Test OpenAI", hint: "Checks the key and model.", provider: "chatgpt" },
      { id: "anthropic", label: "Test Anthropic", hint: "Checks the key and model.", provider: "anthropic" },
      { id: "ollama", label: "Test Ollama", hint: "Checks that the Ollama server answers.", provider: "ollama" },
    ],
    database: [
      { id: "db", label: "Test connection", hint: "Connects and counts the recipes it finds." },
      { id: "dbDetect", label: "Find it over SSH", hint: "Reads Mealie's database settings from its container.", requiresSsh: true },
    ],
  };

  function renderTests(sectionId) {
    const tests = (CONNECTION_TESTS[sectionId] || []).filter((test) => {
      if (test.provider && provider !== test.provider) return false;
      if (test.requiresSsh) return expandedAdvanced.has(sectionId) && Boolean(String(envDraft.MEALIE_DB_SSH_HOST || "").trim());
      return true;
    });
    if (tests.length === 0) return null;
    return (
      <div className="settings-group-tests">
        {tests.map((test) => {
          const state = connectionChecks[test.id] || {};
          const detect = test.id === "dbDetect";
          return (
            <div key={test.id} className="connection-test-item">
              <button
                type="button"
                className="ghost"
                onClick={() => (detect ? runDbDetect() : runConnectionTest(test.id))}
                disabled={state.loading}
              >
                <Icon name={state.loading ? "refresh" : detect ? "search" : "zap"} />
                {state.loading ? (detect ? "Looking…" : "Testing…") : test.label}
              </button>
              <p
                className={`tiny ${state.ok === false ? "danger-text" : state.ok === true ? "success-text" : "muted"}`}
                role={state.detail ? "status" : undefined}
              >
                {state.detail || test.hint}
              </p>
            </div>
          );
        })}
      </div>
    );
  }

  function renderInput(item) {
    const key = String(item.key);
    const hasValue = Boolean(item.has_value);
    const draftValue = envDraft[key] ?? "";
    const onChangeDraft = (next) => {
      setEnvDraft((prev) => ({ ...prev, [key]: next }));
      if (item.secret && envClear[key]) {
        setEnvClear((prev) => ({ ...prev, [key]: false }));
      }
    };

    if (key === "CATEGORIZER_PROVIDER") {
      return (
        <select value={provider} onChange={(e) => onChangeDraft(e.target.value)}>
          <option value="none">Off (rules only)</option>
          <option value="chatgpt">ChatGPT (OpenAI)</option>
          <option value="anthropic">Anthropic</option>
          <option value="ollama">Ollama (Local)</option>
        </select>
      );
    }

    const modelKind = { OPENAI_MODEL: "openai", ANTHROPIC_MODEL: "anthropic", OLLAMA_MODEL: "ollama" }[key];
    if (modelKind) {
      const modelList = availableModels[modelKind] || [];
      return (
        <>
          {modelList.length > 0 ? (
            <select value={draftValue} onChange={(e) => onChangeDraft(e.target.value)}>
              {!draftValue && <option value="">Select a model…</option>}
              {modelList.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          ) : (
            <input type="text" value={draftValue} placeholder={item.default || ""} onChange={(e) => onChangeDraft(e.target.value)} />
          )}
          <button type="button" className="ghost small" onClick={() => fetchAvailableModels(modelKind)}>
            <Icon name="refresh" /> {modelList.length > 0 ? "Refresh list" : "Load models"}
          </button>
        </>
      );
    }

    const choices = Array.isArray(item.choices) ? item.choices : [];
    if (choices.length === 2 && choices.includes("true") && choices.includes("false")) {
      return (
        <select value={draftValue || item.default} onChange={(e) => onChangeDraft(e.target.value)}>
          <option value="true">On</option>
          <option value="false">Off</option>
        </select>
      );
    }
    if (choices.length > 0) {
      return (
        <select value={draftValue} onChange={(e) => onChangeDraft(e.target.value)}>
          {choices.map((c) => (
            <option key={c} value={c}>{c === "" ? "— disabled —" : c}</option>
          ))}
        </select>
      );
    }

    if (key === RUN_DURATION_KEY) {
      const parts = runDurationParts(draftValue);
      const onChangePart = (part, rawValue) => {
        const parsed = Number.parseInt(String(rawValue), 10);
        const hours = part === "hours" ? clampNumber(parsed, 0, 12) : parts.hours;
        const minutes = part === "minutes" ? clampNumber(parsed, 0, 59) : parts.minutes;
        onChangeDraft(String(clampNumber(hours * 60 + minutes, 1, MAX_RUN_DURATION_MINUTES) * 60));
      };
      return (
        <div className="duration-control">
          <label className="duration-part">
            <span>Hours</span>
            <input type="number" min="0" max="12" step="1" inputMode="numeric" value={parts.hours}
              onChange={(e) => onChangePart("hours", e.target.value)} />
          </label>
          <label className="duration-part">
            <span>Minutes</span>
            <input type="number" min="0" max={parts.hours >= 12 ? "0" : "59"} step="1" inputMode="numeric" value={parts.minutes}
              onChange={(e) => onChangePart("minutes", e.target.value)} />
          </label>
        </div>
      );
    }

    return (
      <>
        <input
          type={item.secret ? "password" : "text"}
          autoComplete={item.secret ? "off" : undefined}
          value={draftValue}
          placeholder={item.secret && hasValue && !envClear[key] ? "Saved. Type to replace it." : key === "MEALIE_DB_URL" ? "postgresql://mealie:password@postgres:5432/mealie" : ""}
          onChange={(e) => onChangeDraft(e.target.value)}
        />
        {item.secret && hasValue ? (
          <button
            type="button"
            className="ghost small"
            onClick={() => {
              setEnvDraft((prev) => ({ ...prev, [key]: "" }));
              setEnvClear((prev) => ({ ...prev, [key]: true }));
            }}
            disabled={envClear[key]}
          >
            {envClear[key] ? "Removed when you save" : "Remove"}
          </button>
        ) : null}
      </>
    );
  }

  const movedCount = moved?.imported?.length || 0;
  const showMovedNote = !movedNoteSeen && (movedCount > 0 || moved?.folded_db);

  return (
    <section className="page-grid settings-grid">
      <article className="card">
        <div className="card-head split">
          <p className="muted">How CookDex reaches Mealie and the helpers it can use. Saved changes apply to the next run.</p>
          <div className="settings-head-actions">
            <label className="settings-technical-toggle">
              <input type="checkbox" checked={showTechnical} onChange={toggleTechnical} />
              Show variable names
            </label>
          </div>
        </div>

        {showMovedNote ? (
          <div className="settings-moved-note" role="status">
            <Icon name="info" />
            <p>
              {movedCount > 0
                ? `CookDex copied ${movedCount} setting${movedCount === 1 ? "" : "s"} from your compose file and manages ${movedCount === 1 ? "it" : "them"} here now. You can delete ${movedCount === 1 ? "that line" : "those lines"} from the compose file. `
                : ""}
              {moved?.folded_db ? "Your separate database settings were combined into one connection string. " : ""}
              Only the settings listed under "Stays in the compose file" belong there.
            </p>
            <button type="button" className="ghost small" onClick={() => { writeFlag(MOVED_NOTE_KEY, true); setMovedNoteSeen(true); }}>
              Got it
            </button>
          </div>
        ) : null}

        <div className="settings-groups">
          {sections.map((section) => {
            const isCollapsed = collapsed?.has(section.id) ?? section.id !== "mealie";
            const status = sectionStatus(section.id, envSpecs, envDraft);
            const advancedCount = section.items.filter((item) => ADVANCED_KEYS.has(String(item.key)) && fitsProvider(String(item.key))).length;
            const advancedOpen = expandedAdvanced.has(section.id);
            return (
              <section key={section.id} className={`settings-group ${isCollapsed ? "collapsed" : ""}`}>
                <button type="button" className="settings-group-toggle" onClick={() => toggleSection(section.id)} aria-expanded={!isCollapsed}>
                  <h4><Icon name={section.icon} /> {section.title}</h4>
                  {status.text ? <span className={`status-pill ${status.tone === "ok" ? "success" : status.tone === "warn" ? "warning" : "neutral"}`}>{status.text}</span> : null}
                  <Icon name="chevron" />
                </button>
                {!isCollapsed ? (
                  <div className="settings-rows">
                    <p className="settings-section-blurb">{section.blurb}</p>
                    {section.items.map((item) => {
                      const key = String(item.key);
                      if (!isShown(key, section.id)) return null;
                      const note = sourceNote(item);
                      return (
                        <div key={key} className="settings-row">
                          <div className="settings-labels">
                            <label>{item.label || key}</label>
                            <p>{item.description}</p>
                            {showTechnical || note ? (
                              <div className="meta-line">
                                {showTechnical ? <code>{key}</code> : null}
                                {note ? <span>{note}</span> : null}
                              </div>
                            ) : null}
                          </div>
                          <div className="settings-input-wrap">{renderInput(item)}</div>
                        </div>
                      );
                    })}
                    {advancedCount > 0 ? (
                      <button type="button" className="ghost small settings-advanced-toggle" aria-expanded={advancedOpen} onClick={() => toggleAdvanced(section.id)}>
                        {advancedOpen ? "Show less" : ADVANCED_LABELS[section.id] || `${advancedCount} more setting${advancedCount === 1 ? "" : "s"}`}
                      </button>
                    ) : null}
                    {renderTests(section.id)}
                  </div>
                ) : null}
              </section>
            );
          })}
        </div>

        <div className="settings-save-bar">
          <button className="primary" onClick={saveSettings} disabled={changeCount === 0}>
            <Icon name="save" />
            {changeCount === 0 ? "Saved" : `Save ${changeCount} change${changeCount === 1 ? "" : "s"}`}
          </button>
          {changeCount > 0 ? (
            <button type="button" className="ghost" onClick={loadSettings}>Discard</button>
          ) : null}
        </div>
      </article>

      <aside className="stacked-cards">
        <article className="card">
          <h3><Icon name="info" /> Stays in the compose file</h3>
          <p className="muted">
            Everything on this page is set here. The compose file only needs what the container uses before CookDex starts:
          </p>
          <ul className="settings-deploy-list">
            {DEPLOYMENT_SETTINGS.map(([name, what]) => (
              <li key={name}>
                <code>{name}</code>
                <span className="tiny muted">{what}</span>
              </li>
            ))}
          </ul>
          <p className="tiny muted">
            Older compose files may still set Mealie, AI or database values. CookDex copies them here once; after that, this page wins.
          </p>
        </article>
        <article className="card">
          <h3><Icon name="wand" /> Where AI is used</h3>
          <p className="muted">AI is optional. Rules handle tagging without it. With a provider set up:</p>
          <ul className="ai-task-list">
            <li>
              <strong>Tag and categorize</strong>
              <p className="tiny muted">Suggests categories, tags and tools for recipes the rules don't match.</p>
            </li>
            <li>
              <strong>Ingredient parser</strong>
              <p className="tiny muted">Can hand lines it isn't sure about to Mealie's own OpenAI parser, if that's turned on in Mealie. It doesn't use the provider set here.</p>
            </li>
          </ul>
        </article>
      </aside>
    </section>
  );
}
