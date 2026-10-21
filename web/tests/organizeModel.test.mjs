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

test("only changes that could lose something need a backup first", async () => {
  const { needsBackup } = await import("../src/features/organize/model.mjs");
  assert.equal(needsBackup([{ op: "delete", unused: true }, { op: "create" }]), false);
  assert.equal(needsBackup([{ op: "delete", unused: true }, { op: "delete" }]), true);
  assert.equal(needsBackup([{ op: "merge" }]), true);
  assert.equal(needsBackup([{ op: "rename" }]), true);
});

test("conflicting merges and deletes cannot be applied together", async () => {
  const { dependencyProblem } = await import("../src/features/organize/model.mjs");
  const merge = { op: "merge", kind: "tags", id: "a", target_id: "b" };
  assert.match(dependencyProblem([merge, { op: "delete", kind: "tags", id: "b", unused: true }]), /merge target/);
  assert.equal(dependencyProblem([merge, { op: "delete", kind: "categories", id: "b" }]), "");
});

test("failed backup and canceled runs never report success or discard staged changes", async () => {
  const { applyOutcome } = await import("../src/features/organize/model.mjs");
  for (const status of ["failed", "canceled"]) {
    const outcome = applyOutcome({ status }, { status, results: [] });
    assert.equal(outcome.tone, "warning");
    assert.deepEqual(outcome.applied, []);
    assert.match(outcome.text, /still staged/);
    assert.doesNotMatch(outcome.text, /^Applied 0/);
  }
});

test("cookbook failure remains visible even when individual changes applied", async () => {
  const { applyOutcome } = await import("../src/features/organize/model.mjs");
  const applied = { id: "a", kind: "tags", op: "merge", status: "applied" };
  const outcome = applyOutcome({ status: "failed" }, { results: [{ kind: "taxonomy_change", items: [applied] }] });
  assert.equal(outcome.tone, "warning");
  assert.match(outcome.text, /failed/);
  assert.deepEqual(outcome.applied, [applied]);
});

test("an apply backs up first only when it could lose something, and the person can opt out", async () => {
  const { applyBackupFirst } = await import("../src/features/organize/model.mjs");
  const merge = { op: "merge", kind: "foods", id: "f2", name: "garlic clove", target_id: "f1", target_name: "garlic" };
  const unusedDelete = { op: "delete", kind: "tags", id: "t9", name: "locale: US", unused: true };
  const create = { op: "create", kind: "units", id: "new:1", name: "pinch", to: { name: "pinch" } };
  assert.equal(applyBackupFirst([merge]), true);
  assert.equal(applyBackupFirst([merge], true), true);
  assert.equal(applyBackupFirst([merge], false), false);
  assert.equal(applyBackupFirst([unusedDelete, create]), false);
  assert.equal(applyBackupFirst([unusedDelete, create], true), false);
});

test("an unused label delete needs no backup, a used one does", async () => {
  const { needsBackup } = await import("../src/features/organize/model.mjs");
  assert.equal(needsBackup([{ op: "delete", kind: "labels", id: "l3", name: "Empty", unused: true }]), false);
  assert.equal(needsBackup([{ op: "delete", kind: "labels", id: "l1", name: "Produce", unused: false }]), true);
  assert.equal(needsBackup([{ op: "merge", kind: "labels", id: "l2", name: "produce", target_id: "l1", target_name: "Produce" }]), true);
});

test("unused entries are offered for bulk removal only when some are in use", async () => {
  const { unusedOffer } = await import("../src/features/organize/model.mjs");
  const mixed = unusedOffer([{ id: "a", count: 3 }, { id: "b", count: 0 }, { id: "c", count: 0 }]);
  assert.deepEqual(mixed.unused.map((i) => i.id), ["b", "c"]);
  assert.equal(mixed.canClearAll, true);
  // A fresh library or a just-added starter set: nothing in use yet.
  assert.equal(unusedOffer([{ id: "a", count: 0 }, { id: "b", count: 0 }]).canClearAll, false);
  assert.equal(unusedOffer([{ id: "a", count: 2 }]).canClearAll, false);
  assert.equal(unusedOffer([]).canClearAll, false);
});

test("Mealie's own unused flag wins over a zero count", async () => {
  const { isUnused, onShoppingList, unusedOffer } = await import("../src/features/organize/model.mjs");
  // Mealie 3.28: no flag, so a zero count means unused.
  assert.equal(isUnused({ count: 0 }), true);
  assert.equal(isUnused({ count: 2 }), false);
  assert.equal(isUnused({ count: null }), false);
  // Mealie 3.29: a food on a shopping list has no recipes but isn't unused.
  const listed = { id: "b", count: 0, unused: false };
  assert.equal(isUnused(listed), false);
  assert.equal(onShoppingList(listed), true);
  assert.equal(onShoppingList({ count: 0, unused: true }), false);
  assert.deepEqual(unusedOffer([{ id: "a", count: 3, unused: false }, listed, { id: "c", count: 0, unused: true }]).unused.map((i) => i.id), ["c"]);
});
