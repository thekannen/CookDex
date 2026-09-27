import assert from "node:assert/strict";
import test from "node:test";

import { createChange, normalizeName, packItems } from "../src/features/organize/packs.mjs";

const pack = { kind: "tags", items: [{ name: "Gluten-Free" }, { name: "Salads" }, { name: "Italian" }, { name: "Thai" }] };

test("names normalize like the backend", () => {
  assert.equal(normalizeName("  Café & Bistro's "), "cafe and bistros");
  assert.equal(normalizeName("Gluten-Free"), "gluten free");
});

test("items the library has, or has staged, aren't offered again", () => {
  const items = packItems(pack, ["gluten free", "Salad"], ["italian"]);
  assert.deepEqual(items.map((i) => i.state), ["have", "have", "staged", "new"]);
});

test("pack items become create changes with stable ids", () => {
  assert.deepEqual(createChange("tags", { name: "Middle Eastern" }), {
    op: "create", kind: "tags", id: "new-tags-middle-eastern", name: "Middle Eastern", to: { name: "Middle Eastern" },
  });
  assert.equal(createChange("labels", { name: "Produce", color: "#43a047" }).to.color, "#43a047");
});
