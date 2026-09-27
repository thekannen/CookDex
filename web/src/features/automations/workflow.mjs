// Automations as people think about them: "every Sunday at 8 AM, check the
// library, then clean up the recipe list, and let me review it". Pure
// functions, so they can be tested without a browser.

import { nextOccurrence, WEEKDAYS } from "./schedule.mjs";

export const HOUR = 3600;
export const DAY = 86_400;
export const WEEK = 7 * DAY;

export const EVERY_CHOICES = [
  { value: "manual", label: "Only when I run it" },
  { value: "day", label: "Every day" },
  { value: "week", label: "Every week" },
  { value: "hours", label: "Every few hours" },
  { value: "once", label: "Once" },
];

const pad = (n) => String(n).padStart(2, "0");

function timeOf(date) {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function clockLabel(time) {
  const [h, m] = String(time || "03:00").split(":").map((part) => Number.parseInt(part, 10) || 0);
  return new Date(2000, 0, 1, h, m).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

/** What the builder shows for a stored trigger. */
export function choiceFromTrigger(trigger = {}) {
  const start = trigger.start_at ? new Date(trigger.start_at) : null;
  const time = trigger.time || (start ? timeOf(start) : "03:00");
  const weekday = trigger.weekday ?? (start ? start.getDay() : 0);
  if (trigger.type === "once") {
    const at = trigger.run_at ? new Date(trigger.run_at) : null;
    return { every: "once", time: at ? timeOf(at) : time, weekday, hours: 6, date: at ? `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}` : "" };
  }
  if (trigger.type !== "interval") return { every: "manual", time, weekday, hours: 6, date: "" };
  const seconds = Number(trigger.seconds || 0);
  if (seconds === WEEK) return { every: "week", time, weekday, hours: 6, date: "" };
  if (seconds === DAY) return { every: "day", time, weekday, hours: 6, date: "" };
  return { every: "hours", time, weekday, hours: Math.max(1, Math.round(seconds / HOUR)), date: "" };
}

/** The trigger to store for what the builder shows. start_at is the next local occurrence, in UTC. */
export function triggerFromChoice(choice, now = new Date()) {
  const { every, time = "03:00", weekday = 0, hours = 6, date = "" } = choice || {};
  if (every === "manual") return { type: "manual" };
  if (every === "once") {
    const [h, m] = String(time).split(":").map((part) => Number.parseInt(part, 10) || 0);
    const [y, mo, d] = String(date).split("-").map((part) => Number.parseInt(part, 10));
    const at = y ? new Date(y, mo - 1, d, h, m) : nextOccurrence(time, { now });
    return { type: "once", run_at: at.toISOString(), time };
  }
  if (every === "hours") {
    const seconds = Math.min(Math.max(Number(hours) || 1, 1), 23) * HOUR;
    return { type: "interval", seconds, start_at: new Date(now.getTime() + seconds * 1000).toISOString() };
  }
  const weekly = every === "week";
  return {
    type: "interval",
    seconds: weekly ? WEEK : DAY,
    start_at: nextOccurrence(time, { weekday: weekly ? weekday : null, now }).toISOString(),
    time,
    ...(weekly ? { weekday } : {}),
  };
}

/** "Every Sunday at 8:00 AM" */
export function describeTrigger(trigger = {}) {
  const choice = choiceFromTrigger(trigger);
  if (choice.every === "manual") return "Only when you run it";
  if (choice.every === "once") {
    return trigger.run_at ? `Once, ${new Date(trigger.run_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}` : "Once";
  }
  if (choice.every === "hours") return choice.hours === 1 ? "Every hour" : `Every ${choice.hours} hours`;
  if (choice.every === "day") return `Every day at ${clockLabel(choice.time)}`;
  return `Every ${WEEKDAYS[choice.weekday] || "week"} at ${clockLabel(choice.time)}`;
}

function lowerFirst(text) {
  return text ? text.charAt(0).toLowerCase() + text.slice(1) : text;
}

function list(parts) {
  if (parts.length <= 1) return parts.join("");
  return `${parts.slice(0, -1).join(", ")}, then ${parts[parts.length - 1]}`;
}

// Some jobs read better named after their main dial.
const MERGE_TARGETS = { both: "foods and units", foods: "foods", units: "units", taxonomy: "tags and categories", tags: "tags", categories: "categories" };

/** A step's name, e.g. "Merge duplicate tags and categories". */
export function stepTitle(step, jobTitle) {
  if (step?.task_id === "cleanup-duplicates" && MERGE_TARGETS[step.options?.target]) {
    return `Merge duplicate ${MERGE_TARGETS[step.options.target]}`;
  }
  return jobTitle(step?.task_id);
}

/** One sentence for the whole automation. */
export function describeWorkflow(workflow, jobTitle) {
  const stepList = workflow?.steps || [];
  const steps = stepList.map((step) => lowerFirst(stepTitle(step, jobTitle)));
  const when = describeTrigger(workflow?.trigger);
  const what = steps.length ? list(steps) : "nothing yet";
  const backsUp = stepList.some((step) => step.task_id === "mealie-backup");
  let how = "Preview only: nothing changes until you review it.";
  if (workflow?.mode === "apply") {
    if (workflow?.writes === false || backsUp) how = "";
    else how = workflow?.backup_first !== false ? "Changes are applied, after a backup." : "Changes are applied, with no backup first.";
  }
  const prefix = when === "Only when you run it" ? "When you run it" : when;
  return `${prefix}: ${what}.${how ? ` ${how}` : ""}`;
}

// Short notes about a step's settings, like "rules only" or "up to 25".
const STEP_NOTES = {
  "tag-categorize": (o) => ({ rules: "rules only", ai: "AI only" }[o.method] || ""),
  "recipe-dredger": (o) => (o.max_total ? `up to ${o.max_total}` : ""),
  "mealie-backup": (o) => (o.keep ? `keeps ${o.keep}` : ""),
  "ingredient-parse": (o) => (o.max_recipes ? `up to ${o.max_recipes}` : ""),
  "reimport-recipes": (o) => (o.max_recipes ? `up to ${o.max_recipes}` : ""),
  "clean-recipes": (o) => {
    const off = [o.run_junk === false && "junk", o.run_dedup === false && "duplicates", o.run_names === false && "names"].filter(Boolean);
    return off.length ? `skips ${off.join(", ")}` : "";
  },
};

export function stepNote(step) {
  const note = STEP_NOTES[step?.task_id];
  return note ? note(step.options || {}) : "";
}

/** Step progress from a workflow run's log: [{ index, title, status }]. */
export function stepsFromLog(text, total = 0) {
  const steps = new Map();
  let current = null;
  for (const raw of String(text || "").split(/\r?\n/)) {
    const line = raw.trim();
    if (line.startsWith("[step] ")) {
      try {
        const info = JSON.parse(line.slice(7));
        current = info.index;
        steps.set(info.index, { index: info.index, title: info.title, status: "running" });
      } catch {
        // A malformed marker doesn't stop the rest from showing.
      }
      continue;
    }
    const done = line.match(/^\[done\] Step (\d+):/);
    if (done && steps.has(Number(done[1]))) steps.get(Number(done[1])).status = "done";
    const failed = line.match(/^\[error\] Step (\d+) /);
    if (failed && steps.has(Number(failed[1]))) steps.get(Number(failed[1])).status = "failed";
  }
  const list = [...steps.values()].sort((a, b) => a.index - b.index);
  return { steps: list, current, total };
}
