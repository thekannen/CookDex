import React, { useState } from "react";
import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { DOCS_URL, HELP_GETTING_STARTED, HELP_TOPICS, HELP_TROUBLESHOOTING_URL } from "../../constants";

function DocLink({ href, children }) {
  return (
    <a className="link-btn" href={href} target="_blank" rel="noreferrer">
      <Icon name="external" /> {children}
    </a>
  );
}

export default function HelpPage({ aboutMeta }) {
  const docsUrl = aboutMeta?.links?.docs || DOCS_URL;
  const [debugLog, setDebugLog] = useState(null);
  const [debugLogLoading, setDebugLogLoading] = useState(false);

  async function fetchDebugLog() {
    setDebugLogLoading(true);
    try {
      const data = await api("/debug-log");
      setDebugLog(data);
    } catch (e) {
      setDebugLog({ error: String(e), log: "", log_available: false });
    } finally {
      setDebugLogLoading(false);
    }
  }

  function downloadDebugLog() {
    if (!debugLog) return;
    const h = debugLog.health || {};
    const db = h.db || {};
    const cfg = h.config || {};
    const conns = h.connections || {};
    const runs = h.runs || {};
    const sc = h.scheduler || {};
    const statusCounts = runs.status_counts || {};
    const connLine = (label, c) => `${label.padEnd(12)}${c?.ok ? "OK" : "FAIL"}  ${c?.detail || ""}`;

    const sections = [
      "=== CookDex Debug Report ===",
      `Version:    ${debugLog.app_version || "-"}`,
      `Python:     ${debugLog.python_version || "-"}`,
      `Platform:   ${debugLog.platform || "-"}`,
      `Log file:   ${debugLog.log_file || "-"}`,
      "",
      "=== Connection Tests ===",
      connLine("Mealie", conns.mealie),
      connLine("OpenAI", conns.openai),
      connLine("Anthropic", conns.anthropic),
      connLine("Ollama", conns.ollama),
      connLine("Database connection", conns.direct_db),
      "",
      "=== Instance Health ===",
      `Users:      ${db.user_count ?? "-"}`,
      `Runs total: ${db.run_count ?? "-"}  (${Object.entries(statusCounts).map(([k, v]) => `${k}: ${v}`).join(", ") || "none"})`,
      `Schedules:  ${db.schedule_count ?? "-"} total, ${db.enabled_schedules ?? "-"} enabled`,
      `Scheduler:  ${sc.running ? "running" : "stopped"}`,
      "",
      "=== Configuration ===",
      `Mealie URL:       ${cfg.mealie_url_set ? "set" : "NOT SET"}`,
      `Mealie key:       ${cfg.mealie_key_set ? "set" : "NOT SET"}`,
      `OpenAI key:       ${cfg.openai_key_set ? "set" : "not set"}`,
      `OpenAI model:     ${cfg.openai_model || "(default)"}`,
      `Anthropic key:    ${cfg.anthropic_key_set ? "set" : "not set"}`,
      `Anthropic model:  ${cfg.anthropic_model || "(default)"}`,
      `Ollama URL:       ${cfg.ollama_url_set ? "set" : "not set"}`,
      `Ollama model:     ${cfg.ollama_model || "(default)"}`,
      "",
      "=== Recent Runs ===",
      ...(runs.recent || []).map(r =>
        `${r.started_at || "-"}  ${r.status.padEnd(10)}  ${r.task_id}  (${r.triggered_by})`
      ),
      "",
      "=== Server Log ===",
      debugLog.log || "(no log content)",
    ].join("\n");

    const blob = new Blob([sections], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cookdex-debug.log";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="page-grid settings-grid help-grid">
      <div className="stacked-cards">
        <article className="card">
          <h3>Documentation</h3>
          <p className="muted">The full guide to installing, setting up and using CookDex is on the CookDex site. Each topic below links to its page there.</p>
          <div className="help-links">
            <DocLink href={docsUrl}>Documentation</DocLink>
          </div>
        </article>

        <article className="card">
          <h3>First steps</h3>
          <ol className="getting-started">
            {HELP_GETTING_STARTED.map((step, i) => <li key={i}>{step}</li>)}
          </ol>
          <div className="help-links">
            <DocLink href={`${DOCS_URL}getting-started/`}>Getting started</DocLink>
          </div>
        </article>

        {HELP_TOPICS.map((topic) => (
          <article className="card" key={topic.id}>
            <h3><Icon name={topic.icon} /> {topic.title}</h3>
            <p className="muted">{topic.intro}</p>
            <div className="help-links">
              {topic.links.map((link) => <DocLink key={link.url} href={link.url}>{link.label}</DocLink>)}
            </div>
          </article>
        ))}
      </div>

      <aside className="stacked-cards">
        <article className="card">
          <h3>When something's wrong</h3>
          <p className="muted">Fixes for sign-in, reaching Mealie or its database, jobs that didn't finish, and problems after an update. Each job's details in Recent activity say what happened, and Technical details has the full log.</p>
          <div className="help-links">
            <DocLink href={HELP_TROUBLESHOOTING_URL}>Troubleshooting</DocLink>
          </div>
        </article>

        <article className="card">
          <h3>Report a problem</h3>
          <p className="muted">Make a report to attach to a GitHub issue. Settings show only as set or not set, never their values; the recent server log is included as it is, so read it before you post.</p>

          <div className="debug-actions">
            <a
              className="button ghost"
              href={(aboutMeta?.links?.github || "https://github.com/thekannen/cookdex") + "/issues/new"}
              target="_blank"
              rel="noreferrer"
            >
              <Icon name="external" /> Open a GitHub issue
            </a>

            {!debugLog ? (
              <button className="ghost" type="button" onClick={fetchDebugLog} disabled={debugLogLoading}>
                <Icon name={debugLogLoading ? "refresh" : "list"} />
                {debugLogLoading ? "Making it\u2026" : "Make a report"}
              </button>
            ) : (
              <>
                {debugLog.error ? (
                  <p className="muted tiny" style={{ color: "var(--error, #c0392b)" }}>{debugLog.error}</p>
                ) : (() => {
                  const h = debugLog.health || {};
                  const db = h.db || {};
                  const cfg = h.config || {};
                  const conns = h.connections || {};
                  const runs = h.runs || {};
                  const sc = h.scheduler || {};
                  const counts = runs.status_counts || {};
                  const ConnRow = ({ label, conn, detail }) => (
                    <div className="debug-health-row">
                      <span className="muted tiny">{label}</span>
                      <span className={`status-pill ${conn?.ok ? "success" : conn?.detail === "Not configured" ? "neutral" : "danger"}`}
                        title={conn?.detail || ""}>
                        {conn?.ok ? "OK" : conn?.detail === "Not configured" ? "Not configured" : "Failed"}
                      </span>
                    </div>
                  );
                  return (
                    <>
                      <div className="debug-health-grid">
                        <div className="debug-health-row">
                          <span className="muted tiny">Scheduler</span>
                          <span className={`status-pill ${sc.running ? "success" : "danger"}`}>{sc.running ? "Running" : "Stopped"}</span>
                        </div>
                        <ConnRow label="Mealie" conn={conns.mealie} />
                        <ConnRow label="OpenAI" conn={conns.openai} />
                        <ConnRow label="Anthropic" conn={conns.anthropic} />
                        <ConnRow label="Ollama" conn={conns.ollama} />
                        <ConnRow label="Database connection" conn={conns.direct_db} />
                        <div className="debug-health-row">
                          <span className="muted tiny">Runs</span>
                          <span className="muted tiny">
                            {db.run_count ?? 0} total
                            {counts.failed ? <span style={{ color: "var(--error, #c0392b)", marginLeft: "0.4rem" }}>{counts.failed} failed</span> : null}
                          </span>
                        </div>
                        <div className="debug-health-row">
                          <span className="muted tiny">Schedules</span>
                          <span className="muted tiny">{db.enabled_schedules ?? 0} of {db.schedule_count ?? 0} enabled</span>
                        </div>
                      </div>
                      {!debugLog.log_available ? (
                        <p className="muted tiny">No server log file found yet — logs appear after the first server restart.</p>
                      ) : (
                        <pre className="debug-log-preview">{debugLog.log}</pre>
                      )}
                    </>
                  );
                })()}
                <div className="debug-log-row">
                  <button className="ghost small" type="button" onClick={downloadDebugLog}>
                    <Icon name="download" /> Download report
                  </button>
                  <button className="ghost small" type="button" onClick={() => setDebugLog(null)}>
                    <Icon name="refresh" /> Make it again
                  </button>
                </div>
                {debugLog.app_version && (
                  <p className="muted tiny">v{debugLog.app_version} · {debugLog.platform}</p>
                )}
              </>
            )}
          </div>
        </article>
      </aside>
    </section>
  );
}
