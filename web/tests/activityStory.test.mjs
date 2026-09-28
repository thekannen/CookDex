import assert from "node:assert/strict";
import test from "node:test";

import { describeProgress, isPreview, logProblems, runKind, runStory } from "../src/features/activity/story.mjs";

const healthResults = [
  { source: "cookdex.recipe_quality_audit", summary: { __title__: "Quality Audit", "Total Recipes": 12169, "Gold (5-6/6)": 2509, "Gold %": 20.6, "Silver (3-4/6)": 8892, "Bronze (0-2/6)": 768, "Top Gap": "time" } },
  { source: "cookdex.audit_taxonomy", summary: { __title__: "Taxonomy Audit", "Without Category": 1870, "Without Tags": 3072, "Unused Tags": 0, "Unused Categories": 0, "Problematic Tags": 0 } },
  { source: "cookdex.data_maintenance", summary: { "Stages Run": 2, Passed: 2, Failed: 0 } },
];

test("a health check reads as sentences, not a key/value table", () => {
  const story = runStory({ status: "succeeded", task_id: "health-check", options: {} }, healthResults);
  assert.equal(
    story.headline,
    "20.6% of 12,169 recipes are complete. What's most often missing: cooking times. 1,870 recipes have no category and 3,072 have no tags."
  );
  const quiet = runStory({ status: "succeeded", options: { workflow: { mode: "preview" } } }, [
    ...healthResults,
    { source: "cookdex.recipe_deduplicator", summary: { "Duplicates Found": 0 } },
    { source: "cookdex.recipe_name_normalizer", summary: { Candidates: 0 } },
  ]);
  assert.match(quiet.headline, /2 other checks found nothing to do\. Nothing in Mealie has changed yet\.$/);
  assert.equal(story.sections.length, 2);
  assert.deepEqual(story.sections[0].stats[0], { label: "Complete", value: "2,509", tone: "ok" });
});

test("previews say nothing has changed; applied runs say what changed", () => {
  const summary = { source: "cookdex.rule_tagger", summary: { "Total Assignments": 20800, "Recipes to Update": 10053, "Recipes Updated": 10050, Failed: 3 } };
  const preview = runStory({ status: "succeeded", options: { dry_run: true } }, [summary]);
  assert.equal(preview.headline, "Would add 20,800 tags, categories and tools on 10,053 recipes. Nothing in Mealie has changed yet.");
  const applied = runStory({ status: "succeeded", options: { dry_run: false } }, [summary]);
  assert.equal(applied.headline, "Added 20,800 tags, categories and tools on 10,050 recipes.");
  assert.ok(applied.sections[0].stats.some((s) => s.label === "Couldn't be changed" && s.value === "3"));
});

test("unknown jobs still show their numbers, minus the noise", () => {
  const story = runStory({ status: "succeeded", options: {} }, [{ source: "cookdex.something_new", summary: { __title__: "New Thing", Mode: "apply", Widgets: 4 } }]);
  assert.deepEqual(story.sections[0], { title: "New Thing", headline: "", stats: [{ label: "Widgets", value: "4", tone: undefined }] });
  assert.equal(story.headline, "Finished.");
});

test("failed pipeline steps are called out", () => {
  const story = runStory({ status: "failed", options: { dry_run: true } }, [{ source: "cookdex.data_maintenance", summary: { Failed: 1 } }]);
  assert.equal(story.headline, "1 step didn't finish.");
});

test("preview vs applied and who started it", () => {
  assert.equal(isPreview({ options: { dry_run: true } }), true);
  assert.equal(isPreview({ options: { dry_run: true, apply_cleanups: true } }), false);
  assert.equal(isPreview({ options: {} }), false);
  assert.equal(runKind({ options: { dry_run: true }, triggered_by: "scheduler" }), "Preview · automatic");
  assert.equal(runKind({ options: {}, triggered_by: "aaron" }), "Started by aaron");
});

test("log problems are grouped and errors come first", () => {
  const log = [
    "[info] fine",
    "[warn] Couldn't save 'a': 400",
    "[warn] Couldn't save 'b': 400",
    "[error] Mealie didn't answer",
    "[warn] Couldn't save 'c': 400",
  ].join("\n");
  const { items } = logProblems(log);
  assert.equal(items[0].level, "error");
  assert.equal(items[1].count, 3);
  assert.equal(items[1].message, "Couldn't save 'a': 400");
});

test("progress reads as counts and a percent", () => {
  assert.deepEqual(describeProgress({ label: "Saving", done: 250, total: 1000 }), { label: "Saving", percent: 25, detail: "250 of 1,000" });
  assert.equal(describeProgress(null), null);
});
