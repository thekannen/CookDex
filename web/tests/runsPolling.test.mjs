import assert from "node:assert/strict";
import test from "node:test";

import { ACTIVE_RUNS_MS, IDLE_RUNS_MS, runsRefetchInterval } from "../src/features/activity/runsPolling.mjs";

test("run lists poll quickly while a job is queued or running, slowly otherwise", () => {
  assert.equal(runsRefetchInterval({ items: [{ status: "succeeded" }, { status: "running" }] }), ACTIVE_RUNS_MS);
  assert.equal(runsRefetchInterval({ items: [{ status: "queued" }] }), ACTIVE_RUNS_MS);
  assert.equal(runsRefetchInterval({ items: [{ status: "failed" }, { status: "canceled" }] }), IDLE_RUNS_MS);
  assert.equal(runsRefetchInterval(undefined), IDLE_RUNS_MS);
  assert.ok(ACTIVE_RUNS_MS <= 5000 && IDLE_RUNS_MS <= 30000);
});
