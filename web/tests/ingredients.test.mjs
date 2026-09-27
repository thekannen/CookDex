import assert from "node:assert/strict";
import test from "node:test";

import { ingredientEdit, textToAliases } from "../src/features/organize/ingredients.mjs";

test("aliases are trimmed, deduplicated and never repeat the name", () => {
  assert.deepEqual(textToAliases(" Tbs, T ,tbs,, tablespoon", "Tablespoon"), ["Tbs", "T"]);
  assert.deepEqual(textToAliases("", "cup"), []);
});

test("an edit is staged only when something changed", () => {
  const unit = { id: "u1", name: "tablespoon", plural_name: "tablespoons", abbreviation: "tbsp", aliases: ["Tbs"] };
  assert.equal(ingredientEdit("units", unit, { name: "tablespoon", plural_name: "tablespoons", abbreviation: "tbsp", aliases: ["Tbs"] }), null);
  const change = ingredientEdit("units", unit, { ...unit, aliases: ["Tbs", "T"] });
  assert.equal(change.op, "update");
  assert.deepEqual(change.to.aliases, ["Tbs", "T"]);
  const food = { id: "f1", name: "onion", plural_name: "", label_id: "", aliases: [] };
  assert.equal(ingredientEdit("foods", food, { name: "onion", plural_name: "", label_id: "l1", aliases: [] }).to.label_id, "l1");
});
