import test from "node:test";
import assert from "node:assert/strict";

import {
  contentsText, daysLeft, deletedBy, expiryText, formatBytes, matchesSearch, restoreNotice, restoreOutcome,
} from "../src/features/library/deleted.mjs";

const NOW = Date.parse("2026-10-21T12:00:00Z");

test("sizes read like a person would say them", () => {
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(20_480), "20 KB");
  assert.equal(formatBytes(5 * 1024 * 1024), "5.0 MB");
});

test("days left counts down from the delete date", () => {
  const item = { deleted_at: "2026-10-20T12:00:00Z" };
  assert.equal(daysLeft(item, 30, NOW), 29);
  assert.equal(expiryText(item, 30, NOW), "Kept 29 more days");
  assert.equal(expiryText(item, 1, NOW), "Removed today");
  assert.equal(expiryText({ deleted_at: "2026-10-21T00:00:00Z" }, 1, NOW), "Kept 1 more day");
  assert.equal(daysLeft({}, 30, NOW), null);
});

test("who deleted it", () => {
  assert.equal(deletedBy({ triggered_by: "alex" }), "by alex");
  assert.equal(deletedBy({ triggered_by: "scheduler" }), "by an automation");
  assert.equal(deletedBy({}), "");
});

test("contents line", () => {
  assert.equal(contentsText({ ingredients: 1, steps: 3, has_image: true }), "1 ingredient · 3 steps · photo");
  assert.equal(contentsText({ ingredients: 0, steps: 0 }), "No ingredients or steps");
});

test("search matches name, address and reason", () => {
  const item = { name: "About Us", slug: "about-us", reason: "Utility page slug: 'about'" };
  assert.ok(matchesSearch(item, "utility"));
  assert.ok(matchesSearch(item, ""));
  assert.ok(!matchesSearch(item, "chili"));
});

test("a finished restore is announced plainly", () => {
  const results = [{ kind: "recipe_restore", items: [{ name: "Chili", slug: "chili-1", old_slug: "chili", status: "applied" }] }];
  assert.deepEqual(restoreNotice(restoreOutcome(results)), {
    text: "“Chili” is back in Mealie. Its web address is now chili-1.", tone: "success",
  });
  const mixed = [{ kind: "recipe_restore", items: [
    { name: "A", status: "applied" }, { name: "B", status: "error", error: "Mealie didn't answer." },
  ] }];
  assert.equal(restoreNotice(restoreOutcome(mixed)).text, "1 restored, 1 couldn't be. Mealie didn't answer.");
  assert.equal(restoreNotice(restoreOutcome([])), null);
});
