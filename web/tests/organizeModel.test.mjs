import assert from "node:assert/strict";
import test from "node:test";

import { describeChange, groupChanges, stagedSummary } from "../src/features/organize/model.mjs";

const changes = [
  { op: "delete", kind: "tags", id: "t4", name: "Parser: Needs Review" },
  { op: "merge", kind: "tags", id: "t2", name: "salads", target_id: "t1", target_name: "Salad" },
  { op: "rename", kind: "categories", id: "c1", name: "desserts", to: "Desserts" },
  { op: "merge", kind: "tags", id: "t5", name: "indian food", target_id: "t6", target_name: "Indian" },
];

test("summary counts each kind of change", () => {
  assert.equal(stagedSummary(changes), "4 changes staged: 2 merges, 1 rename, 1 delete");
});

test("descriptions read as sentences", () => {
  assert.equal(describeChange(changes[1]), "Merge “salads” into “Salad”");
  assert.equal(describeChange(changes[2], { short: true }), "→ Desserts");
});

test("changes group by kind and operation, merges first", () => {
  const groups = groupChanges(changes);
  assert.deepEqual(groups.map(([title, items]) => [title, items.length]), [
    ["Tags: merges", 2],
    ["Categories: renames", 1],
    ["Tags: deletions", 1],
  ]);
});
