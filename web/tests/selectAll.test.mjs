import assert from "node:assert/strict";
import test from "node:test";

import { allSelected, withAll } from "../src/components/selectAll.mjs";

test("Select all ticks every listed key and keeps other selections", () => {
  const selected = new Set(["rename:a", "delete:x"]);
  const next = withAll(selected, ["rename:a", "rename:b", "rename:c"], true);
  assert.deepEqual([...next].sort(), ["delete:x", "rename:a", "rename:b", "rename:c"]);
  assert.ok(allSelected(["rename:a", "rename:b", "rename:c"], next));
  // The original set isn't changed.
  assert.equal(selected.size, 2);
});

test("Select none unticks only the listed keys", () => {
  const selected = new Set(["rename:a", "rename:b", "delete:x"]);
  const next = withAll(selected, ["rename:a", "rename:b"], false);
  assert.deepEqual([...next], ["delete:x"]);
  assert.ok(!allSelected(["rename:a", "rename:b"], next));
});

test("An empty list is never all selected", () => {
  assert.ok(!allSelected([], new Set(["rename:a"])));
});
