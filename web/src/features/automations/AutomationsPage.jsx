import React, { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format, formatDistanceToNow } from "date-fns";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { WEEKDAYS, nextOccurrence, whenLabel } from "./schedule.mjs";

const DISCOVER_AMOUNTS = [10, 25, 50, 100];
const RUN_STATUS = {
  succeeded: { label: "Done", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  canceled: { label: "Not run", tone: "neutral" },
  running: { label: "Running", tone: "neutral" },
  queued: { label: "Waiting", tone: "neutral" },
};

// Routines that keep the library tidy without anyone remembering to run them.
export default function AutomationsPage({ isOwner, taskTitle, onOpenTasks, onNotice, onError }) {
  const queryClient = useQueryClient();
  const automations = useQuery({ queryKey: ["automations"], queryFn: () => api("/automations") });
  const history = useQuery({ queryKey: ["runs", "history"], queryFn: () => api("/runs?limit=20"), refetchInterval: 15000 });
  const [consent, setConsent] = useState(null); // routine + settings waiting for approval

  const save = useMutation({
    mutationFn: ({ routine, settings, allowUnattended = false }) =>
      api(`/automations/${routine.id}`, {
        method: "PUT",
        body: {
          enabled: settings.enabled,
          time: settings.time,
          weekday: routine.period === "weekly" ? settings.weekday : null,
          max_total: settings.max_total ?? null,
          start_at: settings.enabled
            ? nextOccurrence(settings.time, { weekday: routine.period === "weekly" ? settings.weekday : null }).toISOString()
            : null,
          allow_unattended: allowUnattended,
        },
      }),
    onSuccess: (data, { routine, settings }) => {
      queryClient.setQueryData(["automations"], data);
      setConsent(null);
      onNotice?.(
        settings.enabled
          ? `“${routine.title}” is on. ${whenLabel({ ...routine, ...settings })}.`
          : `“${routine.title}” is off.`
      );
    },
    onError: (exc) => onError?.(exc),
  });

  function update(routine, settings) {
    if (settings.enabled && routine.writes && !routine.approved) {
      setConsent({ routine, settings });
      return;
    }
    save.mutate({ routine, settings });
  }

  const routines = automations.data?.routines || [];
  const others = automations.data?.other_schedules || [];

  return (
    <section className="automations">
      <header className="organize-head page-head-split">
        <div>
          <h2>Automations</h2>
          <p className="muted">Routines that keep your library tidy on their own. Turn one on and pick when it runs.</p>
        </div>
        <button type="button" className="ghost small" onClick={onOpenTasks}>
          <Icon name="folder" /> All tools
        </button>
      </header>

      {automations.isLoading ? <p className="muted">Loading…</p> : null}
      <div className="routine-list">
        {routines.map((routine) => (
          <RoutineCard key={routine.id} routine={routine} busy={save.isPending} onChange={(settings) => update(routine, settings)} />
        ))}
      </div>

      {others.length ? (
        <section className="library-section" aria-labelledby="other-schedules-title">
          <div className="library-section-head">
            <h3 id="other-schedules-title">Other schedules</h3>
            <button type="button" className="link-inline" onClick={onOpenTasks}>Manage in Tasks</button>
          </div>
          <ul className="activity-list">
            {others.map((schedule) => (
              <li key={schedule.schedule_id}>
                <span className={`status-pill ${schedule.enabled ? "success" : "neutral"}`}>{schedule.enabled ? "On" : "Off"}</span>
                <span>{schedule.name} <span className="muted">· {taskTitle(schedule.task_id)}</span></span>
                <span className="muted tiny">{schedule.next_run_at ? `next ${formatDistanceToNow(new Date(schedule.next_run_at), { addSuffix: true })}` : ""}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="library-section" aria-labelledby="history-title">
        <div className="library-section-head">
          <h3 id="history-title">History</h3>
          <button type="button" className="link-inline" onClick={onOpenTasks}>Logs and details</button>
        </div>
        <ul className="activity-list">
          {(history.data?.items || []).map((run) => {
            const status = RUN_STATUS[run.status] || { label: run.status, tone: "neutral" };
            const writes = run.options?.dry_run === false || run.options?.apply_cleanups;
            return (
              <li key={run.run_id} className="history-row">
                <span className={`status-pill ${status.tone}`}>{status.label}</span>
                <span>
                  {taskTitle(run.task_id)}
                  <span className="muted"> · {run.triggered_by === "scheduler" ? "automatic" : "manual"}{"dry_run" in (run.options || {}) ? (writes ? ", applied" : ", preview") : ""}</span>
                  {run.status !== "succeeded" && run.error ? <span className="history-error">{run.error}</span> : null}
                </span>
                <span className="muted tiny">{run.created_at ? formatDistanceToNow(new Date(run.created_at), { addSuffix: true }) : ""}</span>
              </li>
            );
          })}
        </ul>
      </section>

      <Dialog.Root open={Boolean(consent)} onOpenChange={(open) => { if (!open) setConsent(null); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="sheet-overlay" />
          {consent ? (
            <Dialog.Content className="review-sheet review-sheet-small" aria-describedby="consent-desc">
              <header className="review-sheet-head">
                <div>
                  <Dialog.Title className="review-sheet-title">Let “{consent.routine.title}” change Mealie on its own?</Dialog.Title>
                  <Dialog.Description id="consent-desc" className="muted">
                    {isOwner
                      ? "It will run without asking each time. You can turn it off here, or revoke approval from the task on the Tasks page."
                      : "This routine changes Mealie without asking each time, so an owner has to turn it on."}
                  </Dialog.Description>
                </div>
              </header>
              <footer className="review-sheet-foot">
                <Dialog.Close className="ghost">Cancel</Dialog.Close>
                {isOwner ? (
                  <button
                    type="button"
                    className="primary"
                    disabled={save.isPending}
                    onClick={() => save.mutate({ ...consent, allowUnattended: true })}
                  >
                    Allow and turn on
                  </button>
                ) : null}
              </footer>
            </Dialog.Content>
          ) : null}
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}

function RoutineCard({ routine, busy, onChange }) {
  const [time, setTime] = useState(routine.time);
  const [weekday, setWeekday] = useState(routine.weekday ?? 0);
  const [maxTotal, setMaxTotal] = useState(routine.max_total || 25);
  const settings = { enabled: routine.enabled, time, weekday, max_total: routine.id === "weekly-discover" ? maxTotal : undefined };
  const dirty =
    routine.enabled &&
    (time !== routine.time || (routine.period === "weekly" && weekday !== (routine.weekday ?? 0)) ||
      (routine.id === "weekly-discover" && maxTotal !== (routine.max_total || 25)));
  const last = routine.last_run;

  return (
    <article className={`routine${routine.enabled ? " is-on" : ""}`}>
      <div className="routine-main">
        <label className="routine-toggle">
          <input
            type="checkbox"
            role="switch"
            checked={routine.enabled}
            disabled={busy}
            onChange={() => onChange({ ...settings, enabled: !routine.enabled })}
          />
          <span className="routine-title">{routine.title}</span>
        </label>
        <p className="muted">{routine.description}</p>
        {routine.writes ? (
          <p className="tiny routine-writes">
            <Icon name="shield" /> Changes Mealie without asking each time{routine.id === "nightly-backup" ? " (removes nightly backups older than the newest 7)" : ""}.
          </p>
        ) : null}
      </div>

      <div className="routine-when">
        {routine.period === "weekly" ? (
          <select aria-label={`Day for ${routine.title}`} value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}>
            {WEEKDAYS.map((day, index) => <option key={day} value={index}>{day}s</option>)}
          </select>
        ) : null}
        <input type="time" aria-label={`Time for ${routine.title}`} value={time} onChange={(e) => setTime(e.target.value)} />
        {routine.id === "weekly-discover" ? (
          <select aria-label="Most new recipes per run" value={maxTotal} onChange={(e) => setMaxTotal(Number(e.target.value))}>
            {DISCOVER_AMOUNTS.map((n) => <option key={n} value={n}>up to {n} recipes</option>)}
          </select>
        ) : null}
        {dirty ? (
          <button type="button" className="primary small" disabled={busy} onClick={() => onChange(settings)}>Save</button>
        ) : null}
      </div>

      <p className="routine-status tiny muted">
        {routine.enabled && routine.next_run_at
          ? `Next: ${format(new Date(routine.next_run_at), "EEE, MMM d 'at' p")}`
          : routine.enabled ? "On" : "Off"}
        {last
          ? ` · Last run ${last.status === "succeeded" ? "finished" : last.status === "canceled" ? "was skipped" : "failed"} ${
              last.finished_at ? formatDistanceToNow(new Date(last.finished_at), { addSuffix: true }) : ""
            }`
          : ""}
      </p>
    </article>
  );
}
