import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { ReviewSheet, useRunResult } from "../run-results/RunResultPanel";
import ActivityList from "../activity/ActivityList";
import RunSheet from "../activity/RunSheet";
import { collectItems, filterCollected } from "../run-results/model.mjs";
import { describeStep, stepHeading } from "./scanProgress.mjs";

const FINISHED = new Set(["succeeded", "failed", "canceled"]);

const SCORE_PART_LABELS = {
  category: "Categorized",
  tags: "Tagged",
  ingredients: "Ingredients linked",
  yield: "Servings set",
};

const SEVERITY_ICON = { high: "alertTriangle", medium: "info", low: "tag" };

export function findingTitle(finding) {
  if (finding.count === 1 && finding.title_one) return finding.title_one;
  return String(finding.title || "").replace("{n}", String(finding.count));
}

function useLibrary(poll) {
  return useQuery({
    queryKey: ["library"],
    queryFn: () => api("/library"),
    refetchInterval: poll ? 2000 : false,
  });
}

function useRun(runId) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api(`/runs/${runId}`),
    enabled: Boolean(runId),
    refetchInterval: (query) => (FINISHED.has(query.state.data?.status) ? false : 1500),
  });
}

// Home page: how complete the library is, and a short list of what needs
// attention, each with the one action that fixes it.
export default function LibraryPage({
  isOwner, canApplyCleanup, recentRuns, taskTitle, onOpenTask, onSetup, onRunsChanged, onNotice, onError,
}) {
  const queryClient = useQueryClient();
  const [applyRunId, setApplyRunId] = useState("");
  const [review, setReview] = useState(null); // { runId, groups }

  const applyRun = useRun(applyRunId);
  const applying = Boolean(applyRunId) && !FINISHED.has(applyRun.data?.status);
  const [polling, setPolling] = useState(false);
  const library = useLibrary(polling || applying);
  const data = library.data;

  useEffect(() => {
    setPolling(Boolean(data?.scanning));
    onRunsChanged?.();
  }, [data?.scanning, data?.last_scanned_at]);

  const scan = useMutation({
    mutationFn: () => api("/library/scan", { method: "POST" }),
    onSuccess: () => {
      setPolling(true);
      queryClient.invalidateQueries({ queryKey: ["library"] });
    },
    onError: (exc) => onError?.(exc),
  });

  // After applying fixes, scan again so the list reflects what's left.
  useEffect(() => {
    if (!applyRunId || !FINISHED.has(applyRun.data?.status)) return;
    setApplyRunId("");
    if (applyRun.data.status === "succeeded") {
      onNotice?.("Changes applied. Checking the library again.", { tone: "success" });
    } else {
      onNotice?.("Applying changes didn't finish. Open Tasks to see what happened.", { tone: "warning" });
    }
    scan.mutate();
  }, [applyRunId, applyRun.data?.status]);

  const scanning = Boolean(data?.scanning) || scan.isPending;

  if (library.isLoading) {
    return <section className="library"><p className="muted">Loading your library…</p></section>;
  }

  if (data && !data.connected) {
    return (
      <section className="library">
        <div className="library-empty">
          <Icon name="link" />
          <h2>Connect Mealie to get started</h2>
          <p className="muted">
            CookDex works on your Mealie library. {isOwner ? "It takes a minute." : "Ask an owner to connect it in Settings."}
          </p>
          {isOwner ? <button type="button" className="primary" onClick={onSetup}>Set up</button> : null}
        </div>
      </section>
    );
  }

  const neverScanned = !data?.last_scanned_at;
  const findings = data?.findings || [];

  return (
    <section className="library">
      <header className="library-head">
        <div>
          <h2>Your library</h2>
          <p className="muted">
            {data?.recipes ? `${data.recipes} recipes` : "Not scanned yet"}
            {data?.last_scanned_at ? ` · checked ${formatDistanceToNow(new Date(data.last_scanned_at), { addSuffix: true })}` : ""}
          </p>
        </div>
        <button type="button" className="ghost" onClick={() => scan.mutate()} disabled={scanning || applying}>
          <Icon name={scanning ? "loader" : "refresh"} className={scanning ? "spin" : ""} />
          {scanning ? "Scanning…" : "Scan again"}
        </button>
      </header>

      {scanning && data?.scan_steps?.length ? <ScanProgress steps={data.scan_steps} /> : null}

      {applying ? (
        <p className="library-banner" role="status"><Icon name="loader" className="spin" /> Applying the changes you selected. A Mealie backup runs first.</p>
      ) : null}

      {neverScanned && !scanning ? (
        <div className="library-empty">
          <Icon name="search" />
          <h2>Scan your library</h2>
          <p className="muted">CookDex looks for pages that aren't recipes, duplicates, messy names and missing details. It's a preview; nothing in Mealie changes.</p>
          <button type="button" className="primary" onClick={() => scan.mutate()}>Scan my library</button>
        </div>
      ) : (
        <>
          {data?.score ? <ScoreCard score={data.score} /> : null}

          <section className="library-section" aria-labelledby="attention-title">
            <h3 id="attention-title">Needs attention</h3>
            {scanning && findings.length === 0 ? (
              <p className="muted library-quiet">Findings show up here when the scan finishes.</p>
            ) : data?.needs_scan && findings.length === 0 ? (
              <p className="muted library-quiet">Scan again to see what's left after your last changes.</p>
            ) : findings.length === 0 ? (
              <p className="library-quiet library-clear"><Icon name="check-circle" /> Nothing needs attention right now.</p>
            ) : (
              <ul className="finding-list">
                {findings.map((finding) => (
                  <FindingRow
                    key={finding.id}
                    finding={finding}
                    disabled={applying || scanning}
                    onAction={() => {
                      const action = finding.action || {};
                      if (action.type === "review") setReview({ runId: action.run_id, groups: action.groups });
                      else if (action.type === "task") onOpenTask?.(action.task_id, action.options);
                    }}
                  />
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      <RecentActivity taskTitle={taskTitle} onOpenTasks={() => onOpenTask?.()} canApplyTask={() => canApplyCleanup} onError={onError} />

      {review ? (
        <FindingReview
          review={review}
          canApply={canApplyCleanup}
          onClose={() => setReview(null)}
          onApplied={(run) => {
            setReview(null);
            if (run?.run_id) setApplyRunId(run.run_id);
          }}
          onError={onError}
        />
      ) : null}
    </section>
  );
}

function ScoreCard({ score }) {
  return (
    <section className="library-score" aria-label={`Library score ${score.value} out of 100`}>
      <div className="score-ring" style={{ "--score": score.value }}>
        <span>{score.value}</span>
      </div>
      <div className="score-body">
        <strong>{score.label}</strong>
        <ul className="score-parts">
          {score.parts.map((part) => (
            <li key={part.key}>
              <span>{SCORE_PART_LABELS[part.key] || part.key}</span>
              <span className="score-bar" aria-hidden="true"><span style={{ width: `${part.percent}%` }} /></span>
              <span className="score-pct">{part.percent}%</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function FindingRow({ finding, disabled, onAction }) {
  return (
    <li className={`finding finding-${finding.severity}`}>
      <span className="finding-count" aria-hidden="true">{finding.count}</span>
      <div className="finding-body">
        <strong>{findingTitle(finding)}</strong>
        <span className="muted">
          {finding.examples?.length ? finding.examples.join(" · ") : finding.detail}
        </span>
      </div>
      <button type="button" className="ghost" onClick={onAction} disabled={disabled}>
        <Icon name={SEVERITY_ICON[finding.severity] || "info"} />
        {finding.action?.label || "Open"}
      </button>
    </li>
  );
}

function FindingReview({ review, canApply, onClose, onApplied, onError }) {
  const run = useRun(review.runId);
  const result = useRunResult(run.data);
  const collected = useMemo(
    () => filterCollected(collectItems(result.data?.results), review.groups),
    [result.data, review.groups]
  );
  if (!run.data || !result.data) return null;
  return (
    <ReviewSheet
      key={`${review.runId}-${(review.groups || []).join(",")}`}
      open
      onOpenChange={(open) => { if (!open) onClose(); }}
      run={run.data}
      taskTitle="Clean Recipe Library"
      collected={collected}
      reviewable
      canApply={canApply}
      onApplied={onApplied}
      onError={onError}
    />
  );
}

function RecentActivity({ taskTitle, onOpenTasks, canApplyTask, onError }) {
  const [openRun, setOpenRun] = useState(null);
  return (
    <section className="library-section" aria-labelledby="recent-title">
      <div className="library-section-head">
        <h3 id="recent-title">Recent activity</h3>
        <button type="button" className="link-inline" onClick={onOpenTasks}>All tools</button>
      </div>
      <ActivityList taskTitle={taskTitle} onOpen={setOpenRun} limit={5} emptyText="Nothing has run yet. Scans and jobs show up here." />
      <RunSheet
        runId={openRun}
        open={Boolean(openRun)}
        onOpenChange={(open) => { if (!open) setOpenRun(null); }}
        taskTitle={taskTitle}
        canApply={canApplyTask}
        onError={onError}
      />
    </section>
  );
}

function ScanProgress({ steps }) {
  return (
    <section className="scan-progress" aria-label="Scan progress" aria-live="polite">
      <p className="scan-progress-head">
        <strong>Scanning your library</strong> <span className="muted">{stepHeading(steps)}</span>
      </p>
      <ol className="scan-steps">
        {steps.map((step) => {
          const { state, detail, percent } = describeStep(step);
          return (
            <li key={step.task_id} className={`scan-step is-${state}`}>
              <Icon
                name={state === "done" ? "check-circle" : state === "failed" ? "x-circle" : state === "running" ? "loader" : "clock"}
                className={state === "running" ? "spin" : ""}
              />
              <div className="scan-step-body">
                <span className="scan-step-title">{step.title}</span>
                <span className="muted tiny">{detail}</span>
                {percent != null && state === "running" ? (
                  <span className="scan-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
                    <span style={{ width: `${percent}%` }} />
                  </span>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
