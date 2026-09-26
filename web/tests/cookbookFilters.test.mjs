import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(TEST_DIR, "..");

async function loadUtils(t) {
  globalThis.window = { location: { hostname: "localhost", pathname: "/cookdex" } };
  const vite = await createServer({
    root: WEB_ROOT,
    server: { middlewareMode: true },
    appType: "custom",
    logLevel: "silent",
  });
  t.after(async () => {
    delete globalThis.window;
    await vite.close();
  });
  return vite.ssrLoadModule("/src/utils.jsx");
}

test("cookbook filter rows handle rating comparisons and food labels", async (t) => {
  const { parseQueryFilter, buildQueryFilter, coerceFilterOperator, filterOperatorsFor } = await loadUtils(t);

  const rows = parseQueryFilter(
    'rating >= 4 AND recipe_ingredient.food.label_id IN ["label-1"] AND '
      + 'recipeIngredient.food.label.name NOT IN ["Seafood"] AND tags.id IN ["tag-1"]'
  );
  assert.deepEqual(rows, [
    { field: "rating", operator: ">=", values: ["4"], identifier: "value" },
    { field: "labels", operator: "IN", values: ["label-1"], identifier: "id" },
    { field: "labels", operator: "NOT IN", values: ["Seafood"], identifier: "name" },
    { field: "tags", operator: "IN", values: ["tag-1"], identifier: "id" },
  ]);
  assert.equal(
    buildQueryFilter(rows),
    'rating >= 4 AND recipe_ingredient.food.label_id IN ["label-1"] AND '
      + 'recipeIngredient.food.label.name NOT IN ["Seafood"] AND tags.id IN ["tag-1"]'
  );

  // Mealie's own editor aliases and compact spacing parse too.
  assert.deepEqual(parseQueryFilter('recipeIngredient.food.labelId IN ["l"] AND rating<>"2.5"'), [
    { field: "labels", operator: "IN", values: ["l"], identifier: "id" },
    { field: "rating", operator: "<>", values: ["2.5"], identifier: "value" },
  ]);

  // Blank or out-of-range ratings are dropped instead of producing an invalid filter.
  assert.equal(buildQueryFilter([{ field: "rating", operator: ">=", values: [""] }]), "");
  assert.equal(buildQueryFilter([{ field: "rating", operator: ">=", values: ["7"] }]), "");
  // A list operator carried over from another field is coerced to a comparison.
  assert.equal(buildQueryFilter([{ field: "rating", operator: "IN", values: ["3"] }]), "rating >= 3");

  assert.deepEqual(filterOperatorsFor("rating").map((op) => op.value), [">=", ">", "=", "<>", "<=", "<"]);
  assert.deepEqual(filterOperatorsFor("labels").map((op) => op.value), ["IN", "NOT IN", "CONTAINS ALL"]);
  assert.equal(coerceFilterOperator("tags", ">="), "IN");
  assert.equal(coerceFilterOperator("rating", "<="), "<=");
});
