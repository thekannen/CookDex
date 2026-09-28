import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format, formatDistanceToNow } from "date-fns";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import ActivityList from "../activity/ActivityList";
import RunSheet from "../activity/RunSheet";
import { jobInfo } from "../tools/catalog.mjs";
import WorkflowBuilder from "./WorkflowBuilder";
import { describeWorkflow, stepNote, stepTitle, triggerFromChoice, choiceFromTrigger } from "./workflow.mjs";

// Automations: jobs strung together into workflows that run on their own.
// The list says what each one does in a sentence; the builder edits one.
export default function AutomationsPage({ tasks, isOwner, taskTitle, canApplyTask, onOpenTasks, onConfirm, onNotice, onError }) {
  const queryClient = useQueryClient();
  const automations = useQuery({ queryKey: ["automations"], queryFn: () => api("/automations") });
  const [editing, setEditing] = useState(null); // automation, or {} for a new one
  const [openRun, setOpenRun] = useState(null);
  const refresh = (data) => queryClient.setQueryData(["automations"], data);

  // Owners are asked once before an automation may change Mealie on its own.
  function withApproval(name, send) {
    return send(false).catch((exc) => {
      if (String(exc?.message || "") !== "approval_required") throw exc;
      return new Promise((resolve, reject) => {
        onConfirm({
          message: `Let “${name}” change Mealie on its own each time it runs? You can turn it off or change it here any time.`,
          confirmLabel: "Allow",
          danger: false,
          action: () => send(true).then(resolve, reject),
        });
      });
    });
  }

  const save = useMutation({
    mutationFn: ({ id, body }) =>
      withApproval(body.name, (allow) =>
        api(id ? `/automations/${id}` : "/automations", { method: id ? "PUT" : "POST", body: { ...body, allow_changes: allow } })
      ),
    onSuccess: (data, { body }) => {
      if (!data) return;
      refresh(data);
      setEditing(null);
      onNotice?.(`Saved “${body.name}”.`);
    },
    onError: (exc) => onError?.(exc),
  });

  const toggle = useMutation({
    mutationFn: (item) =>
      withApproval(item.name, (allow) => {
        const turningOn = !item.enabled;
        const trigger = turningOn && item.trigger?.type === "interval" ? triggerFromChoice(choiceFromTrigger(item.trigger)) : null;
        return api(`/automations/${item.id}/enabled`, {
          method: "POST",
          body: { enabled: turningOn, start_at: trigger?.start_at || null, allow_changes: allow },
        });
      }),
    onSuccess: (data) => data && refresh(data),
    onError: (exc) => onError?.(exc),
  });

  const remove = useMutation({
    mutationFn: (item) => api(`/automations/${item.id}`, { method: "DELETE" }),
    onSuccess: (data, item) => {
      refresh(data);
      onNotice?.(`Removed “${item.name}”.`);
    },
    onError: (exc) => onError?.(exc),
  });

  async function runNow(item, preview) {
    try {
      const run = await api(`/automations/${item.id}/run`, { method: "POST", body: { preview, confirmed: isOwner } });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      setOpenRun(run.run_id);
    } catch (exc) {
      onError?.(exc);
    }
  }

  const items = automations.data?.items || [];
  const standard = items.filter((item) => item.builtin);
  const mine = items.filter((item) => !item.builtin);
  const busy = save.isPending || toggle.isPending || remove.isPending;
  const card = (item) => (
    <AutomationCard
      key={item.id}
      item={item}
      taskTitle={taskTitle}
      busy={busy}
      isOwner={isOwner}
      onToggle={() => toggle.mutate(item)}
      onEdit={() => setEditing(item)}
      onRun={(preview) => runNow(item, preview)}
      onRemove={() =>
        onConfirm({
          message: `Remove “${item.name}”? It stops running. Nothing it already did is undone.`,
          confirmLabel: "Remove",
          action: () => remove.mutate(item),
        })
      }
      onOpenRun={setOpenRun}
    />
  );

  return (
    <section className="automations">
      <header className="organize-head page-head-split">
        <div>
          <h2>Automations</h2>
          <p className="muted">Jobs strung together that run on their own. Each says what it will do before it does it.</p>
        </div>
        <div className="head-actions">
          <button type="button" className="ghost small" onClick={onOpenTasks}>
            <Icon name="wrench" /> Tools
          </button>
          <button type="button" className="primary small" onClick={() => setEditing({})}>
            <Icon name="plus" /> New automation
          </button>
        </div>
      </header>

      {automations.isLoading ? <p className="muted">Loading…</p> : null}
      {automations.isError ? <p className="danger-text">Couldn't load automations. {String(automations.error?.message || "")}</p> : null}

      {mine.length ? (
        <section className="library-section" aria-labelledby="mine-title">
          <h3 id="mine-title">Yours</h3>
          <div className="routine-list">{mine.map(card)}</div>
        </section>
      ) : null}

      <section className="library-section" aria-labelledby="standard-title">
        <h3 id="standard-title">Ready-made</h3>
        <p className="muted tiny">They come switched off. Turn one on as it is, or open it to change what it does.</p>
        <div className="routine-list">{standard.map(card)}</div>
      </section>

      <section className="library-section" aria-labelledby="history-title">
        <h3 id="history-title">History</h3>
        <ActivityList
          taskTitle={taskTitle}
          onOpen={setOpenRun}
          limit={60}
          filter={(run) => run.task_id === "workflow" || Boolean(run.schedule_id) || run.triggered_by === "scheduler"}
          emptyText="Automations haven't run yet. Preview now runs one straight away."
        />
      </section>

      {editing ? (
        <WorkflowBuilder
          key={editing.id || "new"}
          workflow={editing.id ? editing : null}
          tasks={tasks}
          jobTitle={taskTitle}
          open
          onOpenChange={(open) => { if (!open) setEditing(null); }}
          onSave={(body) => save.mutate({ id: editing.id, body })}
          busy={save.isPending}
        />
      ) : null}

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

function AutomationCard({ item, taskTitle, busy, isOwner, onToggle, onEdit, onRun, onRemove, onOpenRun }) {
  const last = item.last_run;
  const timed = item.trigger?.type && item.trigger.type !== "manual";
  return (
    <article className={`routine automation${item.enabled ? " is-on" : ""}`}>
      <div className="routine-main">
        <div className="automation-title-row">
          {timed ? (
            <label className="routine-toggle">
              <input
                type="checkbox"
                role="switch"
                checked={item.enabled}
                disabled={busy || (item.needs_approval && !isOwner && !item.enabled)}
                onChange={onToggle}
                aria-label={`${item.name} ${item.enabled ? "on" : "off"}`}
              />
              <span className="routine-title">{item.name}</span>
            </label>
          ) : (
            <span className="routine-title">{item.name}</span>
          )}
          <span className={`status-pill ${item.mode === "apply" && item.writes ? "warning" : "neutral"}`}>
            {item.mode === "apply" && item.writes ? "Applies changes" : "Preview only"}
          </span>
        </div>
        <p className="automation-sentence">{describeWorkflow(item, taskTitle)}</p>
        <ol className="step-chips" aria-label="Steps">
          {(item.steps || []).map((step, index) => {
            const note = stepNote(step);
            return (
              <li key={index}>
                <Icon name={jobInfo({ task_id: step.task_id, title: taskTitle(step.task_id), options: [] }).icon} />
                {stepTitle(step, taskTitle)}
                {note ? <span className="muted"> · {note}</span> : null}
              </li>
            );
          })}
        </ol>
        {item.needs_approval ? (
          <p className="tiny routine-writes">
            <Icon name="shield" /> {isOwner ? "You'll be asked to approve it changing Mealie on its own." : "Changes Mealie, so an owner has to turn it on."}
          </p>
        ) : null}
        {item.problem ? <p className="tiny danger-text">{item.problem}</p> : null}
      </div>
      <div className="routine-when automation-actions">
        <button type="button" className="ghost small" onClick={() => onRun(true)} disabled={busy} title="Runs every step as a preview. Nothing changes.">
          <Icon name="eye" /> Preview now
        </button>
        {item.mode === "apply" && item.writes ? (
          <button type="button" className="ghost small" onClick={() => onRun(false)} disabled={busy || (!isOwner && !item.approved)}>
            <Icon name="play" /> Run now
          </button>
        ) : null}
        <button type="button" className="ghost small" onClick={onEdit} disabled={busy}>
          <Icon name="pencil" /> Edit
        </button>
        {!item.builtin ? (
          <button type="button" className="ghost icon-btn" onClick={onRemove} disabled={busy} aria-label={`Remove ${item.name}`}>
            <Icon name="trash" />
          </button>
        ) : null}
      </div>
      <p className="routine-status tiny muted">
        {timed ? (item.enabled ? (item.next_run_at ? `Next: ${format(new Date(item.next_run_at), "EEE, MMM d 'at' p")}` : "On") : "Off") : "Runs when you start it"}
        {last ? (
          <>
            {" · "}
            <button type="button" className="link-inline" onClick={() => onOpenRun(last.run_id)}>
              last run {last.status === "succeeded" ? "finished" : last.status === "canceled" ? "was skipped" : "didn't finish"}{" "}
              {last.finished_at ? formatDistanceToNow(new Date(last.finished_at), { addSuffix: true }) : ""}
            </button>
          </>
        ) : null}
      </p>
    </article>
  );
}
