import assert from "node:assert/strict";
import test from "node:test";

import { buildRule, describeRows, parseRule, rowsToIds } from "../src/features/organize/cookbooks.mjs";

const lookups = {
  categories: [{ id: "c-dinner", name: "Dinner" }],
  tags: [{ id: "t-thai", name: "Thai" }, { id: "t-spicy", name: "Spicy" }],
  tools: [],
};

test("parses Mealie cookbook filters, both spellings and both identifiers", () => {
  const { rows, editable } = parseRule('recipe_category.id IN ["c-dinner"] AND tags.name CONTAINS ALL ["Thai", "Spicy"]');
  assert.equal(editable, true);
  assert.deepEqual(rows, [
    { field: "categories", operator: "IN", identifier: "id", values: ["c-dinner"] },
    { field: "tags", operator: "CONTAINS ALL", identifier: "name", values: ["Thai", "Spicy"] },
  ]);
  assert.equal(parseRule('recipeCategory.id NOT IN ["x"]').rows[0].operator, "NOT IN");
});

test("filters it can't rebuild safely are marked not editable", () => {
  assert.equal(parseRule('tags.id IN ["a"] OR tags.id IN ["b"]').editable, false);
  assert.equal(parseRule('(tags.id IN ["a"])').editable, false);
  assert.equal(parseRule("rating >= 4").editable, false);
  assert.equal(parseRule('recipeIngredient.food.id IN ["f"]').editable, false);
});

test("rebuilds by id and round-trips", () => {
  const rows = rowsToIds(parseRule('tags.name IN ["Thai"] AND recipe_category.id IN ["c-dinner"]').rows, lookups);
  const rule = buildRule(rows);
  assert.equal(rule, 'tags.id IN ["t-thai"] AND recipe_category.id IN ["c-dinner"]');
  assert.deepEqual(parseRule(rule).rows, rows);
});

test("describes rules in words and flags deleted items", () => {
  const described = describeRows(parseRule('recipe_category.id IN ["c-dinner"] AND tags.id IN ["gone"]').rows, lookups);
  assert.deepEqual(described, [
    { field: "Category", operator: "is any of", values: [{ label: "Dinner", missing: false }] },
    { field: "Tag", operator: "is any of", values: [{ label: "Missing tag", missing: true }] },
  ]);
});

test("values with quotes and backslashes survive a round trip", () => {
  const rows = [{ field: "tags", operator: "IN", values: ['Mom\'s "best"', "C:\\", "a\\\"b"] }];
  const rule = buildRule(rows);
  assert.deepEqual(parseRule(rule).rows[0].values, rows[0].values);
});
