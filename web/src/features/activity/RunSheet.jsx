import React, { useEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import RunResultPanel from "../run-results/RunResultPanel";
import StopRunButton from "./StopRunButton";
import StructuredLog from "./StructuredLog";
import { REVIEWABLE_TASKS } from "../run-results/model.mjs";
import { describeProgress, duration, isQuiet, logProblems, runKind, runStory, runTitle, statusOf } from "./story.mjs";
import { stepTitle, stepsFromLog } from "../automations/workflow.mjs";

const LIVE = new Set(["queued", "running"]);

// Everything about one run, readable first: what happened in a sentence, the
// numbers that matter, what went wrong. The raw log is one click away.
export default function RunSheet({ runId, open, onOpenChange, taskTitle, canApply, onApplyForReal, onError }) {
  const runQuery = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api(`/runs/${runId}`),
    enabled: open && Boolean(runId),
    refetchInterval: (query) => (LIVE.has(query.state.data?.status) ? 2000 : false),
  });
  const run = runQuery.data;
  const finished = run && !LIVE.has(run.status);
  const resultQuery = useQuery({
    queryKey: ["run-result", runId, run?.status],
    queryFn: () => api(`/runs/${runId}/result`),
    enabled: open && Boolean(finished),
    staleTime: Infinity,
  });
  const isWorkflow = run?.task_id === "workflow";
  // The technical output is read while a job runs only when someone is looking
  // at it (automations always, since their steps come from it).
  const [logOpen, setLogOpen] = useState(false);
  const logRef = useRef(null);
  useEffect(() => setLogOpen(false), [runId, open]);
  const followLog = !finished && (isWorkflow || logOpen);
  const logQuery = useQuery({
    queryKey: ["run-log", runId, run?.status],
    queryFn: () => api(`/runs/${runId}/log`, { timeout: 60000 }),
    enabled: open && Boolean(run) && Boolean(finished || followLog),
    staleTime: finished ? Infinity : 0,
    refetchInterval: followLog ? 2500 : false,
  });

  function showLog() {
    setLogOpen(true);
    window.requestAnimationFrame(() => logRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  const story = useMemo(() => (run && finished ? runStory(run, resultQuery.data?.results) : null), [run, finished, resultQuery.data]);
  const problems = useMemo(() => logProblems(typeof logQuery.data === "string" ? logQuery.data : ""), [logQuery.data]);
  const status = statusOf(run);
  const title = run ? runTitle(run, taskTitle) : "Run";
  const workflowSteps = isWorkflow ? stepsFromLog(typeof logQuery.data === "string" ? logQuery.data : "") : null;
  const plannedSteps = run?.options?.workflow?.steps || [];
  const progress = describeProgress(run?.progress);
  const allowed = typeof canApply === "function" ? (run ? canApply(run.task_id) : false) : Boolean(canApply);
  const offerApply =
    Boolean(onApplyForReal) && allowed && story?.preview && run?.status === "succeeded" &&
    !REVIEWABLE_TASKS.has(run.task_id) && run.task_id !== "workflow" && story.sections.some((s) => !isQuiet(s.headline));

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="review-sheet run-sheet" aria-describedby="run-sheet-kind">
          <header className="review-sheet-head">
            <div>
              <Dialog.Title className="review-sheet-title">{title}</Dialog.Title>
              <p id="run-sheet-kind" className="muted">
                {run ? runKind(run) : "Loading…"}
                {run?.created_at ? ` · ${format(new Date(run.created_at), "EEE, MMM d 'at' p")}` : ""}
                {run?.started_at ? ` · took ${duration(run)}` : ""}
              </p>
            </div>
            <div className="run-sheet-head-side">
              {run ? (
                <button type="button" className="ghost small" onClick={showLog}>
                  <Icon name="list" /> Technical output
                </button>
              ) : null}
              {run ? <span className={`status-pill ${status.tone}`}>{status.label}</span> : null}
              <Dialog.Close className="ghost icon-btn" aria-label="Close">
                <Icon name="x" />
              </Dialog.Close>
            </div>
          </header>

          <div className="review-sheet-body">
            {run && !finished ? (
              <section className="run-live" aria-live="polite">
                <p className="run-headline">
                  <Icon name="loader" className="spin" /> {run.status === "queued" ? "Waiting for the job before it to finish…" : progress?.label || "Working…"}
                </p>
                {progress?.percent != null ? (
                  <>
                    <span className="scan-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress.percent}>
                      <span style={{ width: `${progress.percent}%` }} />
                    </span>
                    <p className="muted tiny">{progress.detail}</p>
                  </>
                ) : null}
                <div className="run-live-foot">
                  <p className="muted tiny">You can close this; the job keeps going and shows up in Activity.</p>
                  <StopRunButton runIds={[run.run_id]} what={run.status === "queued" ? "this job before it starts" : "this job"} onError={onError} />
                </div>
              </section>
            ) : null}

            {isWorkflow && plannedSteps.length ? (
              <ol className="run-steps">
                {plannedSteps.map((step, index) => {
                  const seen = workflowSteps?.steps.find((item) => item.index === index + 1);
                  const state = seen?.status || (finished ? "skipped" : "waiting");
                  return (
                    <li key={index} className={`is-${state}`}>
                      <Icon
                        name={state === "done" ? "check-circle" : state === "failed" ? "x-circle" : state === "running" ? "loader" : "clock"}
                        className={state === "running" ? "spin" : ""}
                      />
                      <span>{stepTitle(step, taskTitle)}</span>
                      <span className="muted tiny">
                        {{ done: "done", failed: "didn't finish", running: "running", waiting: "waiting", skipped: "didn't run" }[state]}
                      </span>
                    </li>
                  );
                })}
              </ol>
            ) : null}

            {story ? (
              <>
                <p className={`run-headline ${run.status === "failed" ? "danger-text" : ""}`}>{story.headline}</p>
                {run.status === "failed" && run.error ? <p className="run-error">{run.error}</p> : null}
                {story.sections.map((section, index) => (
                  <section key={index} className="run-section">
                    {story.sections.length > 1 ? <h4>{section.title}</h4> : null}
                    {section.stats.length ? (
                      <dl className="run-stats">
                        {section.stats.map((item) => (
                          <div key={item.label} className={item.tone ? `is-${item.tone}` : ""}>
                            <dt>{item.label}</dt>
                            <dd>{item.value}</dd>
                          </div>
                        ))}
                      </dl>
                    ) : null}
                  </section>
                ))}
                <RunResultPanel run={run} taskTitle={taskTitle} canApply={allowed} onError={onError} />
              </>
            ) : null}

            {problems.items.length ? (
              <section className="run-problems">
                <h4>Worth a look</h4>
                <ul>
                  {problems.items.map((item) => (
                    <li key={`${item.level}:${item.message}`} className={item.level === "error" ? "is-error" : ""}>
                      <Icon name={item.level === "error" ? "x-circle" : "alert-triangle"} />
                      <span>
                        {item.message}
                        {item.count > 1 ? <span className="muted"> ({item.count} times, similar)</span> : null}
                      </span>
                    </li>
                  ))}
                </ul>
                {problems.more ? <p className="muted tiny">And {problems.more} more in the technical log.</p> : null}
              </section>
            ) : null}

            {run ? (
              <TechnicalLog
                ref={logRef}
                run={run}
                live={!finished}
                open={logOpen}
                onOpenChange={setLogOpen}
                text={typeof logQuery.data === "string" ? logQuery.data : ""}
              />
            ) : null}
          </div>

          {offerApply ? (
            <footer className="review-sheet-foot">
              <span className="muted tiny">Happy with the preview? Apply it to make these changes in Mealie.</span>
              <button type="button" className="primary" onClick={() => onApplyForReal(run)}>
                <Icon name="check-circle" /> Apply these changes
              </button>
            </footer>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

const TechnicalLog = React.forwardRef(function TechnicalLog({ run, text, live, open, onOpenChange }, ref) {
  const [copied, setCopied] = useState(false);
  const [raw, setRaw] = useState(false);
  const logEnd = useRef(null);
  // While the job runs, keep the newest lines in view.
  useEffect(() => {
    if (live && open) logEnd.current?.scrollIntoView({ block: "nearest" });
  }, [text, live, open, raw]);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be blocked; the text is still selectable below.
    }
  }
  return (
    <details ref={ref} className="run-technical" open={open} onToggle={(e) => onOpenChange?.(e.currentTarget.open)}>
      <summary>Technical details{live ? " (updating)" : ""}</summary>
      <p className="muted tiny">
        Job <code>{run.task_id}</code> · options <code>{JSON.stringify(run.options || {})}</code> · run <code>{run.run_id}</code>
        {run.exit_code != null ? <> · exit code <code>{run.exit_code}</code></> : null}
      </p>
      <div className="run-technical-actions">
        <button type="button" className="ghost small" onClick={copy} disabled={!text}>
          <Icon name="copy" /> {copied ? "Copied" : "Copy log"}
        </button>
        <a className="ghost small button-link" href={`data:text/plain;charset=utf-8,${encodeURIComponent(text)}`} download={`cookdex-${run.task_id}-${run.run_id.slice(0, 8)}.log`}>
          <Icon name="download" /> Download
        </a>
        <button type="button" className="ghost small" aria-pressed={raw} onClick={() => setRaw((value) => !value)} disabled={!text}>
          {raw ? "Readable view" : "Raw text"}
        </button>
      </div>
      {!text ? (
        <p className="muted tiny">{live ? "No output yet." : "No log was recorded."}</p>
      ) : raw ? (
        <pre className="run-log">
          {text}
          <span ref={logEnd} />
        </pre>
      ) : (
        <div className="log-box run-log-readable" role="log">
          <StructuredLog text={text} isLive={live} />
          <span ref={logEnd} />
        </div>
      )}
    </details>
  );
});
