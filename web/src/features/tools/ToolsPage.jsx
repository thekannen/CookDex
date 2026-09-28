import React, { useEffect, useMemo } from "react";

import Icon from "../../components/Icon";
import ActivityList from "../activity/ActivityList";
import { groupJobs } from "./catalog.mjs";
import { useJobRunner } from "./useJobRunner";

// Everything CookDex can do, as jobs grouped by what you want to get done.
// Each job previews first; applying and scheduling are one step further.
export default function ToolsPage({ tasks, isOwner, taskTitle, handoff, clearHandoff, onOpenClassic, onOpenAutomations, onConfirm, onNotice, onError }) {
  const groups = useMemo(() => groupJobs(tasks), [tasks]);
  const { openJob, setJob, setOpenRun, sheets } = useJobRunner({ tasks, isOwner, taskTitle, onConfirm, onNotice, onError });

  // Other pages hand a job over with options already chosen.
  useEffect(() => {
    if (!handoff?.task_id) return;
    const task = tasks.find((t) => t.task_id === handoff.task_id);
    if (task) openJob(task.task_id, handoff.options || {});
    clearHandoff?.();
  }, [handoff, tasks, clearHandoff]);

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

      {sheets}
    </section>
  );
}
