import React, { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

import Icon from "../../components/Icon";
import { fieldFromOption } from "../../utils.jsx";
import { buildTaskOptionSeed } from "../../pages/tasks/taskLogUtils.jsx";
import { groupJobs, jobInfo, splitOptions } from "../tools/catalog.mjs";
import { WEEKDAYS } from "./schedule.mjs";
import { EVERY_CHOICES, choiceFromTrigger, describeWorkflow, stepNote, stepTitle, triggerFromChoice } from "./workflow.mjs";

const MODE_KEYS = new Set(["dry_run", "backup_first", "apply_cleanups"]);

function cleanOptions(options) {
  const out = {};
  for (const [key, value] of Object.entries(options || {})) {
    if (MODE_KEYS.has(key) || value === "" || value === null || value === undefined) continue;
    out[key] = value;
  }
  return out;
}

let nextKey = 1;
const withKey = (step) => ({ ...step, key: nextKey++ });

// Build an automation: when it runs, what it does to Mealie, and its steps,
// each a job with its own dials. The sentence at the top says it all back.
export default function WorkflowBuilder({ workflow, tasks, jobTitle, open, onOpenChange, onSave, busy }) {
  const byId = useMemo(() => new Map(tasks.map((task) => [task.task_id, task])), [tasks]);
  const [name, setName] = useState(workflow?.name || "");
  const [choice, setChoice] = useState(() => choiceFromTrigger(workflow?.trigger || { type: "interval", seconds: 7 * 86400, time: "08:00", weekday: 0 }));
  const [mode, setMode] = useState(workflow?.mode || "preview");
  const [backupFirst, setBackupFirst] = useState(workflow?.backup_first !== false);
  const [stopOnError, setStopOnError] = useState(workflow?.stop_on_error !== false);
  const [enabled, setEnabled] = useState(workflow ? Boolean(workflow.enabled) : true);
  const [steps, setSteps] = useState(() => (workflow?.steps || []).map(withKey));
  const [picking, setPicking] = useState(!workflow?.steps?.length);
  const [openStep, setOpenStep] = useState(null);

  const draft = { name, trigger: triggerFromChoice(choice), mode, backup_first: backupFirst, steps };
  const sentence = describeWorkflow(draft, jobTitle);
  const catalog = useMemo(() => groupJobs(tasks.filter((t) => !t.hidden)), [tasks]);

  function addStep(taskId) {
    const step = withKey({ task_id: taskId, options: {} });
    setSteps((prev) => [...prev, step]);
    setOpenStep(step.key);
    setPicking(false);
    if (!name) setName(jobTitle(taskId));
  }

  function move(index, delta) {
    setSteps((prev) => {
      const next = [...prev];
      const [item] = next.splice(index, 1);
      next.splice(index + delta, 0, item);
      return next;
    });
  }

  function save() {
    onSave({
      name: name.trim() || "My automation",
      description: workflow?.description || "",
      enabled,
      trigger: draft.trigger,
      mode,
      backup_first: backupFirst,
      stop_on_error: stopOnError,
      steps: steps.map((step) => ({ task_id: step.task_id, options: cleanOptions(step.options) })),
    });
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="review-sheet builder-sheet" aria-describedby="builder-sentence">
          <header className="review-sheet-head">
            <div className="builder-head">
              <Dialog.Title className="review-sheet-title">{workflow ? "Edit automation" : "New automation"}</Dialog.Title>
              <input
                className="builder-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Name it, like “Sunday tidy-up”"
                aria-label="Automation name"
                maxLength={80}
              />
              <p id="builder-sentence" className="builder-sentence">{sentence}</p>
            </div>
            <Dialog.Close className="ghost icon-btn" aria-label="Close">
              <Icon name="x" />
            </Dialog.Close>
          </header>

          <div className="review-sheet-body builder-body">
            <section className="builder-block" aria-labelledby="builder-when">
              <h4 id="builder-when"><Icon name="clock" /> When it runs</h4>
              <div className="job-schedule-row">
                <select aria-label="How often" value={choice.every} onChange={(e) => setChoice((c) => ({ ...c, every: e.target.value }))}>
                  {EVERY_CHOICES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
                {choice.every === "week" ? (
                  <select aria-label="Day" value={choice.weekday} onChange={(e) => setChoice((c) => ({ ...c, weekday: Number(e.target.value) }))}>
                    {WEEKDAYS.map((day, index) => <option key={day} value={index}>on {day}</option>)}
                  </select>
                ) : null}
                {choice.every === "hours" ? (
                  <label className="inline-number">
                    every
                    <input type="number" min="1" max="23" value={choice.hours} onChange={(e) => setChoice((c) => ({ ...c, hours: Number(e.target.value) }))} />
                    hours
                  </label>
                ) : null}
                {choice.every === "once" ? (
                  <input type="date" aria-label="Date" value={choice.date} onChange={(e) => setChoice((c) => ({ ...c, date: e.target.value }))} />
                ) : null}
                {["day", "week", "once"].includes(choice.every) ? (
                  <input type="time" aria-label="Time" value={choice.time} onChange={(e) => setChoice((c) => ({ ...c, time: e.target.value }))} />
                ) : null}
              </div>
              {choice.every !== "manual" ? (
                <label className="field checkbox-field">
                  <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
                  <span>Turned on</span>
                </label>
              ) : null}
            </section>

            <section className="builder-block" aria-labelledby="builder-each">
              <h4 id="builder-each"><Icon name="shield" /> Each time it runs</h4>
              <div className="builder-modes" role="radiogroup" aria-label="Preview or apply">
                <label className={mode === "preview" ? "is-picked" : ""}>
                  <input type="radio" name="builder-mode" checked={mode === "preview"} onChange={() => setMode("preview")} />
                  <span><strong>Preview</strong><span className="muted tiny">Shows what it would change. You review and apply.</span></span>
                </label>
                <label className={mode === "apply" ? "is-picked" : ""}>
                  <input type="radio" name="builder-mode" checked={mode === "apply"} onChange={() => setMode("apply")} />
                  <span><strong>Apply changes</strong><span className="muted tiny">Makes the changes on its own. An owner approves this once.</span></span>
                </label>
              </div>
              <div className="builder-toggles">
                {mode === "apply" ? (
                  <label className="field checkbox-field">
                    <input type="checkbox" checked={backupFirst} onChange={(e) => setBackupFirst(e.target.checked)} />
                    <span>Back up Mealie before the first step</span>
                  </label>
                ) : null}
                <label className="field checkbox-field">
                  <input type="checkbox" checked={stopOnError} onChange={(e) => setStopOnError(e.target.checked)} />
                  <span>Stop if a step doesn't finish</span>
                </label>
              </div>
            </section>

            <section className="builder-block" aria-labelledby="builder-steps">
              <h4 id="builder-steps"><Icon name="list" /> Steps</h4>
              <ol className="step-list">
                {steps.map((step, index) => {
                  const task = byId.get(step.task_id);
                  const info = task ? jobInfo(task) : { icon: "wrench", title: step.task_id, blurb: "" };
                  const isOpen = openStep === step.key;
                  const note = stepNote(step);
                  return (
                    <li key={step.key} className={`step-card${isOpen ? " is-open" : ""}`}>
                      <div className="step-card-head">
                        <span className="step-number">{index + 1}</span>
                        <span className="job-icon"><Icon name={info.icon} /></span>
                        <button type="button" className="step-card-title" onClick={() => setOpenStep(isOpen ? null : step.key)} aria-expanded={isOpen}>
                          <strong>{task ? stepTitle(step, jobTitle) : info.title}</strong>
                          <span className="muted tiny">{note || (task ? "Default settings" : "This job isn't available any more")}</span>
                        </button>
                        <div className="step-card-tools">
                          <button type="button" className="ghost icon-btn" aria-label="Move up" disabled={index === 0} onClick={() => move(index, -1)}>
                            <Icon name="chevron" className="chev-up" />
                          </button>
                          <button type="button" className="ghost icon-btn" aria-label="Move down" disabled={index === steps.length - 1} onClick={() => move(index, 1)}>
                            <Icon name="chevron" className="chev-down" />
                          </button>
                          <button type="button" className="ghost icon-btn" aria-label={`Remove ${info.title}`} onClick={() => setSteps((prev) => prev.filter((s) => s.key !== step.key))}>
                            <Icon name="trash" />
                          </button>
                        </div>
                      </div>
                      {isOpen && task ? (
                        <StepDials task={task} options={step.options} onChange={(options) => setSteps((prev) => prev.map((s) => (s.key === step.key ? { ...s, options } : s)))} />
                      ) : null}
                    </li>
                  );
                })}
              </ol>
              {picking ? (
                <div className="step-picker">
                  {catalog.map((goal) => (
                    <div key={goal.id} className="step-picker-group">
                      <p className="muted tiny">{goal.title}</p>
                      <div className="step-picker-grid">
                        {goal.jobs.map(({ task, info }) => (
                          <button key={task.task_id} type="button" className="ghost small step-picker-item" onClick={() => addStep(task.task_id)} disabled={task.available === false}>
                            <Icon name={info.icon} /> {info.title}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                  {steps.length ? <button type="button" className="ghost small" onClick={() => setPicking(false)}>Cancel</button> : null}
                </div>
              ) : (
                <button type="button" className="ghost builder-add" onClick={() => setPicking(true)} disabled={steps.length >= 12}>
                  <Icon name="plus" /> Add a step
                </button>
              )}
            </section>
          </div>

          <footer className="review-sheet-foot">
            <Dialog.Close className="ghost">Cancel</Dialog.Close>
            <button type="button" className="primary" onClick={save} disabled={busy || !steps.length}>
              <Icon name="save" /> Save automation
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function StepDials({ task, options, onChange }) {
  const values = useMemo(() => buildTaskOptionSeed(task, options), [task, options]);
  const { main, more } = useMemo(() => splitOptions(task), [task]);
  const set = (key, value) => onChange({ ...values, [key]: value });
  const fields = (list) => list.map((option) => fieldFromOption(option, values[option.key], set, values));
  const info = jobInfo(task);
  return (
    <div className="step-dials">
      <p className="muted tiny">{info.blurb}</p>
      {main.length ? <div className="option-grid">{fields(main)}</div> : null}
      {more.length ? (
        <details className="job-more">
          <summary>More options ({more.length})</summary>
          <div className="option-grid option-grid-advanced">{fields(more)}</div>
        </details>
      ) : null}
      {!main.length && !more.length ? <p className="muted tiny">Nothing to set for this step.</p> : null}
    </div>
  );
}
