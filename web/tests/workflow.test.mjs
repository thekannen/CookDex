import assert from "node:assert/strict";
import test from "node:test";

import { DAY, WEEK, choiceFromTrigger, describeTrigger, describeWorkflow, stepNote, stepsFromLog, triggerFromChoice } from "../src/features/automations/workflow.mjs";

const titles = { "health-check": "Check library health", "clean-recipes": "Clean up the recipe list", "mealie-backup": "Back up Mealie" };
const jobTitle = (id) => titles[id] || id;

test("weekly and daily choices round-trip through a stored trigger", () => {
  const now = new Date(2030, 0, 1, 12, 0); // a Tuesday
  const weekly = triggerFromChoice({ every: "week", time: "08:30", weekday: 0 }, now);
  assert.equal(weekly.seconds, WEEK);
  assert.equal(new Date(weekly.start_at).getDay(), 0);
  assert.deepEqual(choiceFromTrigger(weekly), { every: "week", time: "08:30", weekday: 0, hours: 6, date: "" });
  const daily = triggerFromChoice({ every: "day", time: "03:00" }, now);
  assert.equal(daily.seconds, DAY);
  assert.equal(choiceFromTrigger(daily).every, "day");
  assert.deepEqual(triggerFromChoice({ every: "manual" }), { type: "manual" });
});

test("converted schedules without hints read from start_at", () => {
  const start = new Date(2030, 0, 6, 7, 15);
  const choice = choiceFromTrigger({ type: "interval", seconds: WEEK, start_at: start.toISOString() });
  assert.equal(choice.every, "week");
  assert.equal(choice.time, "07:15");
  assert.equal(choice.weekday, 0);
  assert.equal(choiceFromTrigger({ type: "interval", seconds: 6 * 3600 }).hours, 6);
});

test("triggers read like a person would say them", () => {
  assert.equal(describeTrigger({ type: "manual" }), "Only when you run it");
  assert.match(describeTrigger({ type: "interval", seconds: WEEK, time: "08:00", weekday: 0 }), /^Every Sunday at 8:00/);
  assert.equal(describeTrigger({ type: "interval", seconds: 3600 }), "Every hour");
});

test("the whole automation is one sentence", () => {
  const sentence = describeWorkflow(
    { trigger: { type: "manual" }, mode: "preview", steps: [{ task_id: "health-check" }, { task_id: "clean-recipes" }] },
    jobTitle
  );
  assert.equal(sentence, "When you run it: check library health, then clean up the recipe list. Preview only: nothing changes until you review it.");
  const apply = describeWorkflow({ trigger: { type: "manual" }, mode: "apply", backup_first: true, steps: [{ task_id: "clean-recipes" }] }, jobTitle);
  assert.match(apply, /Changes are applied, after a backup\.$/);
});

test("step notes summarize the dials", () => {
  assert.equal(stepNote({ task_id: "tag-categorize", options: { method: "rules" } }), "rules only");
  assert.equal(stepNote({ task_id: "clean-recipes", options: { run_names: false } }), "skips names");
  assert.equal(stepNote({ task_id: "health-check", options: {} }), "");
});

test("step progress comes from the run log", () => {
  const log = [
    '[step] {"index": 1, "total": 2, "task_id": "health-check", "title": "Health Check"}',
    "[done] Step 1: Health Check",
    '[step] {"index": 2, "total": 2, "task_id": "clean-recipes", "title": "Clean Recipe Library"}',
    "[error] Step 2 (Clean Recipe Library) didn't finish (exit 1).",
  ].join("\n");
  const { steps } = stepsFromLog(log);
  assert.deepEqual(steps.map((s) => s.status), ["done", "failed"]);
});

test("a step can be named after its main dial", async () => {
  const { stepTitle } = await import("../src/features/automations/workflow.mjs");
  assert.equal(stepTitle({ task_id: "cleanup-duplicates", options: { target: "taxonomy" } }, jobTitle), "Merge duplicate tags and categories");
  assert.equal(stepTitle({ task_id: "health-check", options: {} }, jobTitle), "Check library health");
  const backup = describeWorkflow({ trigger: { type: "manual" }, mode: "apply", backup_first: false, steps: [{ task_id: "mealie-backup" }] }, jobTitle);
  assert.equal(backup, "When you run it: back up Mealie.");
});
