import assert from "node:assert/strict";
import test from "node:test";

import { describeStep, stepHeading } from "../src/features/library/scanProgress.mjs";

test("a running step shows its label, counts and percent", () => {
  const step = { status: "running", progress: { label: "Checking recipes for pages that aren't recipes", done: 4000, total: 12169 } };
  assert.deepEqual(describeStep(step), {
    state: "running",
    detail: "Checking recipes for pages that aren't recipes · 4,000 of 12,169",
    percent: 33,
  });
});

test("other states read plainly", () => {
  assert.equal(describeStep({ status: "queued" }).detail, "Waiting");
  assert.equal(describeStep({ status: "running", progress: null }).detail, "Starting…");
  assert.equal(describeStep({ status: "succeeded" }).state, "done");
  assert.equal(describeStep({ status: "failed" }).detail, "Didn't finish");
});

test("the heading names the step in progress", () => {
  assert.equal(stepHeading([{ status: "succeeded" }, { status: "running" }, { status: "queued" }]), "Step 2 of 3");
  assert.equal(stepHeading([{ status: "succeeded" }, { status: "succeeded" }]), "Finishing up");
});
