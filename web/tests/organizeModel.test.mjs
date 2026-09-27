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

test("cookbook changes read naturally", () => {
  const create = { op: "create", kind: "cookbooks", id: "new-1", name: "Weeknight", to: { name: "Weeknight" } };
  const update = { op: "update", kind: "cookbooks", id: "c1", name: "Salads", to: { name: "Big Salads" } };
  assert.equal(describeChange(create), "Create cookbook “Weeknight”");
  assert.equal(describeChange(update), "Update cookbook “Salads” (renamed to “Big Salads”)");
  assert.equal(stagedSummary([create, update]), "2 changes staged: 1 new, 1 edit");
  assert.deepEqual(groupChanges([update, create]).map(([title]) => title), ["Cookbooks: new", "Cookbooks: edits"]);
});

test("label create and update wording", () => {
  assert.equal(describeChange({ op: "create", kind: "labels", name: "Bakery", to: { name: "Bakery", color: "#aa0000" } }), "Create label “Bakery”");
  assert.equal(describeChange({ op: "update", kind: "labels", name: "Produce", to: { name: "Fruit & Veg", color: "#00aa00" } }), "Rename label “Produce” to “Fruit & Veg”");
  assert.equal(describeChange({ op: "update", kind: "labels", name: "Dairy", to: { name: "Dairy", color: "#0000aa" } }, { short: true }), "Recolored");
  assert.equal(describeChange({ op: "merge", kind: "labels", name: "Spices", target_name: "Pantry" }), "Merge “Spices” into “Pantry”");
});

test("food and unit wording", () => {
  assert.equal(describeChange({ op: "create", kind: "units", name: "dash", to: { name: "dash" } }), "Create unit “dash”");
  assert.equal(describeChange({ op: "update", kind: "foods", name: "onion", to: { name: "Onion" } }), "Rename food “onion” to “Onion”");
  assert.equal(describeChange({ op: "update", kind: "units", name: "cup", to: { name: "cup", aliases: ["c"] } }, { short: true }), "Edited");
  assert.equal(describeChange({ op: "merge", kind: "foods", name: "onions", target_name: "onion" }), "Merge “onions” into “onion”");
});

test("new tags from a starter pack", () => {
  assert.equal(describeChange({ op: "create", kind: "categories", name: "Brunch", to: { name: "Brunch" } }), "Create category “Brunch”");
  assert.equal(describeChange({ op: "create", kind: "tags", name: "Thai", to: { name: "Thai" } }, { short: true }), "New");
});
