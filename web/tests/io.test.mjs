import assert from "node:assert/strict";
import test from "node:test";

import { bundleFiles, exportFileName, summaryLines } from "../src/features/organize/io.mjs";

test("files combine into one bundle", () => {
  const { bundle, problems } = bundleFiles([
    { name: "tags.json", data: [{ name: "Thai" }] },
    { name: "cookdex-taxonomy.json", data: { format: "cookdex-taxonomy", tags: [{ name: "Greek" }], labels: [] } },
    { name: "notes.json", data: [1, 2] },
    { name: "settings.json", data: { theme: "dark" } },
  ]);
  assert.deepEqual(bundle, { tags: [{ name: "Thai" }, { name: "Greek" }], labels: [] });
  assert.equal(problems.length, 2);
});

test("export file names carry the date", () => {
  assert.equal(exportFileName(new Date("2026-09-27T12:00:00Z")), "cookdex-taxonomy-2026-09-27.json");
});

test("summary lines read naturally", () => {
  assert.deepEqual(summaryLines({ tags: { new: 3, updated: 0, unchanged: 12 }, units: { new: 0, updated: 1, unchanged: 0 } }), [
    "Tags: 3 new, 12 already there",
    "Units: 1 to update",
  ]);
});
