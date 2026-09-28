import assert from "node:assert/strict";
import test from "node:test";

import {
  applyLabel,
  applyOptions,
  buildPlan,
  collectItems,
  defaultSelection,
  describeResult,
  hasItems,
} from "../src/features/run-results/model.mjs";

const previewResults = [
  { source: "cookdex.recipe_deduplicator", kind: "recipe_delete", items: [
    { slug: "guacamole-1", name: "Guacamole (1)", group: "duplicate", keep_name: "Guacamole", status: "planned" },
  ] },
  { source: "cookdex.recipe_junk_filter", kind: "recipe_delete", items: [
    { slug: "privacy-policy", name: "Privacy Policy", group: "junk", reason: "Utility page", status: "planned" },
    { slug: "gift-guide", name: "Gift Guide", group: "review", reason: "High-risk keyword", status: "planned" },
  ] },
  { source: "cookdex.recipe_name_normalizer", kind: "recipe_rename", items: [
    { slug: "banana-bread-2", old_name: "banana-bread-2", new_name: "Banana Bread", status: "planned" },
  ] },
  { source: "cookdex.data_maintenance", summary: { "Stages Run": 3 } },
];

test("preview selects junk, duplicates and renames, but not review candidates", () => {
  const collected = collectItems(previewResults);
  assert.equal(hasItems(collected), true);
  assert.deepEqual([...defaultSelection(collected)].sort(), [
    "delete:guacamole-1", "delete:privacy-policy", "rename:banana-bread-2",
  ]);
  assert.equal(
    describeResult(collected, { preview: true }),
    "Preview found 1 entry isn't a recipe, 1 to decide on, 1 duplicate and 1 name to clean up. Nothing in Mealie has changed yet."
  );
});

test("plan carries only selected items and edited names", () => {
  const collected = collectItems(previewResults);
  const selected = new Set(["delete:gift-guide", "delete:guacamole-1", "rename:banana-bread-2"]);
  const plan = buildPlan(collected, selected, { "banana-bread-2": "Grandma's Banana Bread " });
  assert.deepEqual(plan, {
    dedup: { delete: ["guacamole-1"] },
    junk: { delete: ["gift-guide"] },
    names: { rename: { "banana-bread-2": { from: "banana-bread-2", to: "Grandma's Banana Bread" } } },
  });
  assert.equal(applyLabel(plan), "Remove 2 recipes and rename 1 recipe");
  assert.equal(applyLabel(buildPlan(collected, new Set())), "Nothing selected");
});

test("apply options turn the preview live with a backup", () => {
  const options = applyOptions({ dry_run: true, run_dedup: true, backup_first: undefined }, { junk: { delete: [] } });
  assert.equal(options.dry_run, false);
  assert.equal(options.backup_first, true);
  assert.equal(options.run_dedup, true);
});

test("applied result sentence counts applied and failed items", () => {
  const collected = collectItems([
    { kind: "recipe_delete", items: [
      { slug: "a", group: "junk", status: "applied" },
      { slug: "b", group: "duplicate", status: "error" },
      { slug: "c", group: "review", status: "skipped" },
    ] },
    { kind: "recipe_rename", items: [{ slug: "d", old_name: "d", new_name: "D", status: "applied" }] },
  ]);
  assert.equal(
    describeResult(collected, { preview: false }),
    "Applied: removed 1 recipe and renamed 1 recipe. 1 change failed; see details."
  );
});

test("a recipe removed in the batch is not also renamed", () => {
  const collected = collectItems([
    { kind: "recipe_delete", items: [{ slug: "chili-1", name: "chili-1", group: "duplicate", status: "planned" }] },
    { kind: "recipe_rename", items: [{ slug: "chili-1", old_name: "chili-1", new_name: "Chili", status: "planned" }] },
  ]);
  const plan = buildPlan(collected, defaultSelection(collected));
  assert.deepEqual(plan.names.rename, {});
  assert.equal(applyLabel(plan), "Remove 1 recipe");
});

test("filtering keeps only the requested groups", async () => {
  const { filterCollected } = await import("../src/features/run-results/model.mjs");
  const collected = collectItems(previewResults);
  const onlyJunk = filterCollected(collected, ["junk"]);
  assert.equal(onlyJunk.deleteGroups.junk.length, 1);
  assert.equal(onlyJunk.deleteGroups.duplicate.length, 0);
  assert.equal(onlyJunk.renames.length, 0);
  const plan = buildPlan(onlyJunk, defaultSelection(onlyJunk));
  assert.deepEqual(plan.junk.delete, ["privacy-policy"]);
  assert.deepEqual(plan.dedup.delete, []);
  assert.equal(filterCollected(collected, ["rename"]).renames.length, 1);
});

test("renames that repeat another recipe's name start unticked", () => {
  const collected = {
    deleteGroups: { junk: [], duplicate: [], review: [] },
    renames: [
      { slug: "a", old_name: "plum jam recipe", new_name: "Plum Jam Recipe", status: "planned" },
      { slug: "b", old_name: "Plum Jam (No Peel!)", new_name: "Plum Jam", status: "planned", conflict: "existing", conflict_with: "Plum Jam" },
    ],
  };
  const selected = defaultSelection(collected);
  assert.ok(selected.has("rename:a"));
  assert.ok(!selected.has("rename:b"));
});

test("an automation's cleanup step can be reviewed and applied on its own", async () => {
  const { reviewTarget, runWasPreview } = await import("../src/features/run-results/model.mjs");
  const run = {
    task_id: "workflow",
    options: { workflow: { mode: "preview", steps: [
      { task_id: "health-check", options: {} },
      { task_id: "clean-recipes", options: { dry_run: true, backup_first: false, run_names: false } },
    ] } },
  };
  assert.equal(runWasPreview(run), true);
  assert.deepEqual(reviewTarget(run), { task_id: "clean-recipes", options: { dry_run: true, run_names: false } });
  assert.equal(reviewTarget({ task_id: "workflow", options: { workflow: { steps: [{ task_id: "health-check" }] } } }), null);
  assert.deepEqual(reviewTarget({ task_id: "clean-recipes", options: { dry_run: true } }), { task_id: "clean-recipes", options: { dry_run: true } });
});
