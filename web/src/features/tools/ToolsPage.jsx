import React, { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import ActivityList from "../activity/ActivityList";
import RunSheet from "../activity/RunSheet";
import JobSheet from "./JobSheet";
import { groupJobs, runOptions } from "./catalog.mjs";

// Everything CookDex can do, as jobs grouped by what you want to get done.
// Each job previews first; applying and scheduling are one step further.
export default function ToolsPage({ tasks, isOwner, taskTitle, handoff, clearHandoff, onOpenClassic, onOpenAutomations, onConfirm, onNotice, onError }) {
  const queryClient = useQueryClient();
  const groups = useMemo(() => groupJobs(tasks), [tasks]);
  const [job, setJob] = useState(null); // { task, options }
  const [openRun, setOpenRun] = useState(null);
  const [busy, setBusy] = useState(false);

  // Other pages hand a job over with options already chosen.
  useEffect(() => {
    if (!handoff?.task_id) return;
    const task = tasks.find((t) => t.task_id === handoff.task_id);
    if (task) setJob({ task, options: handoff.options || {} });
    clearHandoff?.();
  }, [handoff, tasks, clearHandoff]);

  async function run(task, options, { confirmed = false } = {}) {
    setBusy(true);
    try {
      const created = await api("/runs", { method: "POST", body: { task_id: task.task_id, options, confirmed } });
      setJob(null);
      setOpenRun(created.run_id);
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    } catch (exc) {
      onError(exc);
    } finally {
      setBusy(false);
    }
  }

  async function schedule(task, body) {
    const send = (allow) => api("/automations", { method: "POST", body: { ...body, allow_changes: allow } });
    const done = () => {
      setJob(null);
      queryClient.invalidateQueries({ queryKey: ["automations"] });
      onNotice(`“${body.name}” will run automatically. Find it under Automations.`);
    };
    setBusy(true);
    try {
      await send(false);
      done();
    } catch (exc) {
      if (String(exc?.message || "") === "approval_required") {
        onConfirm({
          message: `Let “${body.name}” change Mealie on its own each time it runs? A backup is made first. You can pause or change it under Automations.`,
          confirmLabel: "Allow and save",
          danger: false,
          action: async () => {
            try {
              await send(true);
              done();
            } catch (err) {
              onError(err);
            }
          },
        });
      } else {
        onError(exc);
      }
    } finally {
      setBusy(false);
    }
  }

  // From a finished preview: the same job, for real.
  function applyForReal(previewRun) {
    const task = tasks.find((t) => t.task_id === previewRun.task_id);
    if (!task) return;
    const options = runOptions(task, previewRun.options, { apply: true });
    const go = () => run(task, options, { confirmed: isOwner });
    onConfirm({
      message: `Apply “${taskTitle(task.task_id)}” to Mealie now? It makes the same changes the preview found${options.backup_first ? ", after a backup" : ""}.`,
      confirmLabel: "Apply changes",
      danger: false,
      action: go,
    });
  }

  const canApplyTask = (taskId) => isOwner || Boolean(tasks.find((t) => t.task_id === taskId)?.policy?.allow_dangerous);

  return (
    <section className="tools-page">
      <header className="organize-head page-head-split">
        <div>
          <h2>Tools</h2>
          <p className="muted">Everything CookDex can do, one job at a time. Previews never change anything.</p>
        </div>
        <button type="button" className="ghost small" onClick={onOpenAutomations}>
          <Icon name="calendar" /> Automations
        </button>
      </header>

      {groups.map((goal) => (
        <section key={goal.id} className="tool-goal" aria-labelledby={`goal-${goal.id}`}>
          <div className="tool-goal-head">
            <h3 id={`goal-${goal.id}`}>{goal.title}</h3>
            <p className="muted tiny">{goal.blurb}</p>
          </div>
          <div className="tool-grid">
            {goal.jobs.map(({ task, info }) => (
              <button
                key={task.task_id}
                type="button"
                className={`tool-card${task.available === false ? " is-unavailable" : ""}`}
                onClick={() => setJob({ task, options: {} })}
              >
                <span className="job-icon"><Icon name={info.icon} /></span>
                <span className="tool-card-text">
                  <strong>{info.title}</strong>
                  <span className="muted tiny">{info.blurb}</span>
                  {task.available === false ? <span className="tiny danger-text">{task.unavailable_reason}</span> : null}
                </span>
                <span className={`tool-kind tiny ${info.kind}`}>
                  {info.kind === "changes" ? "Preview first" : info.kind === "check" ? "Only looks" : "One click"}
                </span>
              </button>
            ))}
          </div>
        </section>
      ))}

      <section className="tool-goal" aria-labelledby="tools-activity">
        <div className="tool-goal-head">
          <h3 id="tools-activity">Recent activity</h3>
          <p className="muted tiny">What ran, and what it found or changed. Select one for details.</p>
        </div>
        <ActivityList taskTitle={taskTitle} onOpen={(runId) => setOpenRun(runId)} limit={15} />
      </section>

      <p className="muted tiny tools-classic">
        Want every option and the raw log side by side? <button type="button" className="link-inline" onClick={onOpenClassic}>Open the classic view</button>.
      </p>

      {job ? (
        <JobSheet
          key={job.task.task_id}
          task={job.task}
          initialOptions={job.options}
          open
          onOpenChange={(open) => { if (!open) setJob(null); }}
          isOwner={isOwner}
          busy={busy}
          onRun={run}
          onSchedule={schedule}
        />
      ) : null}

      <RunSheet
        runId={typeof openRun === "string" ? openRun : null}
        open={Boolean(openRun)}
        onOpenChange={(open) => { if (!open) setOpenRun(null); }}
        taskTitle={taskTitle}
        canApply={canApplyTask}
        onApplyForReal={applyForReal}
        onError={onError}
      />
    </section>
  );
}
