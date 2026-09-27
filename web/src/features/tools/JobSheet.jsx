import React, { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

import Icon from "../../components/Icon";
import { fieldFromOption } from "../../utils.jsx";
import { buildTaskOptionSeed } from "../../pages/tasks/taskLogUtils.jsx";
import { WEEKDAYS } from "../automations/schedule.mjs";
import { triggerFromChoice } from "../automations/workflow.mjs";
import { jobInfo, runOptions, splitOptions } from "./catalog.mjs";

// One job: what it does, the choices that matter, and three ways to run it:
// preview (changes nothing), apply, or on a schedule.
export default function JobSheet({ task, initialOptions, open, onOpenChange, isOwner, onRun, onSchedule, busy }) {
  const info = jobInfo(task);
  const [values, setValues] = useState(() => buildTaskOptionSeed(task, initialOptions || {}));
  const [showMore, setShowMore] = useState(false);
  const [step, setStep] = useState("choose"); // choose | confirm-apply | schedule
  const [backupFirst, setBackupFirst] = useState(true);
  const [when, setWhen] = useState({ every: "week", weekday: 0, time: "03:00", apply: false });
  const { main, more } = useMemo(() => splitOptions(task), [task]);
  const approved = Boolean(task.policy?.allow_dangerous);
  const canApply = isOwner || approved;
  const hasBackup = (task.options || []).some((o) => o.key === "backup_first");
  const changes = info.kind === "changes";

  const setValue = (key, value) => setValues((prev) => ({ ...prev, [key]: value }));
  const fields = (options) => options.map((option) => fieldFromOption(option, values[option.key], setValue, values));

  function start(apply) {
    const options = runOptions(task, values, { apply });
    if (apply && hasBackup) options.backup_first = backupFirst;
    onRun(task, options, { confirmed: apply && isOwner });
  }

  function schedule() {
    const apply = changes ? when.apply : true;
    const options = runOptions(task, values, { apply });
    for (const key of ["dry_run", "backup_first", "apply_cleanups"]) delete options[key];
    onSchedule(task, {
      name: info.title,
      enabled: true,
      trigger: triggerFromChoice({ every: when.every, time: when.time, weekday: when.weekday }),
      mode: apply ? "apply" : "preview",
      backup_first: true,
      stop_on_error: true,
      steps: [{ task_id: task.task_id, options }],
    });
  }

  const unavailable = task.available === false;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="review-sheet job-sheet" aria-describedby="job-sheet-blurb">
          <header className="review-sheet-head">
            <div className="job-sheet-title">
              <span className="job-icon"><Icon name={info.icon} /></span>
              <div>
                <Dialog.Title className="review-sheet-title">{info.title}</Dialog.Title>
                <p id="job-sheet-blurb" className="muted">{info.blurb}</p>
              </div>
            </div>
            <Dialog.Close className="ghost icon-btn" aria-label="Close">
              <Icon name="x" />
            </Dialog.Close>
          </header>

          <div className="review-sheet-body">
            {unavailable ? <p className="danger-text">{task.unavailable_reason || "This job isn't available right now."}</p> : null}
            {task.task_id === "reimport-recipes" ? (
              <p className="job-caution">
                <Icon name="alert-triangle" /> Replaces each recipe's name, ingredients, steps, times and nutrition with what the website has now. Edits you made to those are lost; tags, categories and favorites stay.
              </p>
            ) : null}

            {main.length ? <div className="option-grid job-choices">{fields(main)}</div> : null}

            {more.length ? (
              <details className="job-more" open={showMore} onToggle={(e) => setShowMore(e.currentTarget.open)}>
                <summary>More options ({more.length})</summary>
                <div className="option-grid option-grid-advanced">{fields(more)}</div>
              </details>
            ) : null}

            {step === "confirm-apply" ? (
              <section className="job-confirm" aria-live="polite">
                <h4><Icon name="zap" /> Apply changes to Mealie?</h4>
                <p className="muted">
                  {changes
                    ? "This makes the changes right away, without a review step. To see them first, run a preview instead."
                    : "This runs now."}
                </p>
                {hasBackup ? (
                  <label className="field checkbox-field">
                    <input type="checkbox" checked={backupFirst} onChange={(e) => setBackupFirst(e.target.checked)} />
                    <span>Back up Mealie first (recommended)</span>
                  </label>
                ) : null}
              </section>
            ) : null}

            {step === "schedule" ? (
              <section className="job-schedule">
                <h4><Icon name="calendar" /> Run it automatically</h4>
                <div className="job-schedule-row">
                  <select aria-label="How often" value={when.every} onChange={(e) => setWhen((w) => ({ ...w, every: e.target.value }))}>
                    <option value="day">Every day</option>
                    <option value="week">Every week</option>
                  </select>
                  {when.every === "week" ? (
                    <select aria-label="Day" value={when.weekday} onChange={(e) => setWhen((w) => ({ ...w, weekday: Number(e.target.value) }))}>
                      {WEEKDAYS.map((day, index) => <option key={day} value={index}>on {day}</option>)}
                    </select>
                  ) : null}
                  <input type="time" aria-label="Time" value={when.time} onChange={(e) => setWhen((w) => ({ ...w, time: e.target.value }))} />
                </div>
                {changes ? (
                  <fieldset className="job-schedule-mode">
                    <legend className="muted tiny">Each time it runs</legend>
                    <label>
                      <input type="radio" name="schedule-mode" checked={!when.apply} onChange={() => setWhen((w) => ({ ...w, apply: false }))} />
                      <span><strong>Preview</strong> <span className="muted">and let me review what it finds</span></span>
                    </label>
                    <label>
                      <input type="radio" name="schedule-mode" checked={when.apply} onChange={() => setWhen((w) => ({ ...w, apply: true }))} />
                      <span>
                        <strong>Apply</strong> <span className="muted">the changes on its own, with a backup first</span>
                        <span className="tiny muted"> · {isOwner ? "you'll be asked to approve this once" : "only an owner can set this up"}</span>
                      </span>
                    </label>
                  </fieldset>
                ) : null}
                <p className="muted tiny">It becomes an automation. Find it under Automations, where you can add more steps, pause it or remove it.</p>
              </section>
            ) : null}
          </div>

          <footer className="review-sheet-foot job-actions">
            {step === "choose" ? (
              <>
                <button type="button" className="ghost" onClick={() => setStep("schedule")} disabled={unavailable}>
                  <Icon name="calendar" /> Run automatically…
                </button>
                <div className="job-actions-main">
                  {changes ? (
                    <>
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => setStep("confirm-apply")}
                        disabled={unavailable || !canApply || busy}
                        title={canApply ? "" : "An owner has to approve changes from this job."}
                      >
                        Apply now…
                      </button>
                      <button type="button" className="primary" onClick={() => start(false)} disabled={unavailable || busy}>
                        <Icon name="eye" /> Preview
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="primary"
                      onClick={() => start(true)}
                      disabled={unavailable || busy || (info.kind === "action" && !canApply && Boolean(values.keep))}
                    >
                      <Icon name={info.kind === "check" ? "shield" : "play"} /> {info.kind === "check" ? "Run check" : "Run now"}
                    </button>
                  )}
                </div>
              </>
            ) : null}
            {step === "confirm-apply" ? (
              <>
                <button type="button" className="ghost" onClick={() => setStep("choose")}>Back</button>
                <button type="button" className="primary danger-ish" onClick={() => start(true)} disabled={busy}>
                  <Icon name="zap" /> Apply changes
                </button>
              </>
            ) : null}
            {step === "schedule" ? (
              <>
                <button type="button" className="ghost" onClick={() => setStep("choose")}>Back</button>
                <button type="button" className="primary" onClick={schedule} disabled={busy || (changes && when.apply && !isOwner)}>
                  <Icon name="calendar" /> Save automation
                </button>
              </>
            ) : null}
          </footer>
          {changes && step === "choose" ? (
            <p className="job-footnote muted tiny">A preview shows what would change and changes nothing. You can apply it from there.</p>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
