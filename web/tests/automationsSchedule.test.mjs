import assert from "node:assert/strict";
import test from "node:test";

import { nextOccurrence } from "../src/features/automations/schedule.mjs";

test("daily: later today, or tomorrow if the time has passed", () => {
  const now = new Date(2030, 0, 9, 10, 0); // Wed 10:00 local
  assert.deepEqual(nextOccurrence("12:30", { now }), new Date(2030, 0, 9, 12, 30));
  assert.deepEqual(nextOccurrence("03:00", { now }), new Date(2030, 0, 10, 3, 0));
});

test("weekly: the next matching weekday, never today if already passed", () => {
  const now = new Date(2030, 0, 9, 10, 0); // Wednesday
  assert.deepEqual(nextOccurrence("08:00", { weekday: 0, now }), new Date(2030, 0, 13, 8, 0)); // Sunday
  assert.deepEqual(nextOccurrence("08:00", { weekday: 3, now }), new Date(2030, 0, 16, 8, 0)); // next Wednesday
  assert.deepEqual(nextOccurrence("18:00", { weekday: 3, now }), new Date(2030, 0, 9, 18, 0)); // later today
});
