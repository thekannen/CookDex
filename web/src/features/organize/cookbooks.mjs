// Reading and writing cookbook filters for the Organize page. Pure, so it
// can be tested in Node. Filters are Mealie query strings such as
//   recipe_category.id IN ["…"] AND tags.id CONTAINS ALL ["…", "…"]

export const RULE_FIELDS = [
  { key: "categories", label: "Category", plural: "categories", attr: "recipe_category.id", pattern: /^\s*(?:recipe_?[Cc]ategory|recipeCategory)\.(id|name)\s+/i },
  { key: "tags", label: "Tag", plural: "tags", attr: "tags.id", pattern: /^\s*tags\.(id|name)\s+/i },
  { key: "tools", label: "Tool", plural: "tools", attr: "tools.id", pattern: /^\s*tools\.(id|name)\s+/i },
];

export const RULE_OPERATORS = [
  { value: "IN", label: "is any of" },
  { value: "CONTAINS ALL", label: "has all of" },
  { value: "NOT IN", label: "is none of" },
];

function parseValues(list) {
  const values = [];
  const re = /"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'/g;
  let match;
  while ((match = re.exec(list)) !== null) values.push((match[1] ?? match[2]).replace(/\\(.)/g, "$1"));
  return values;
}

// Parse a filter into editable rows. `editable` is false when any part of the
// filter isn't a simple "field operator [values]" clause joined by AND (for
// example OR, parentheses, ratings, foods), so the UI must not rebuild it.
export function parseRule(rule) {
  const raw = String(rule || "").trim();
  if (!raw) return { rows: [], editable: true };
  if (/\bOR\b|[()]/i.test(raw)) return { rows: [], editable: false };
  const rows = [];
  for (const clause of raw.split(/\s+AND\s+/i)) {
    const field = RULE_FIELDS.find((f) => f.pattern.test(clause));
    const op = clause.match(/\b(NOT\s+IN|CONTAINS\s+ALL|IN)\s*\[([^\]]*)\]\s*$/i);
    if (!field || !op) return { rows: [], editable: false };
    const identifier = clause.match(field.pattern)[1].toLowerCase();
    rows.push({
      field: field.key,
      operator: op[1].toUpperCase().replace(/\s+/g, " "),
      identifier,
      values: parseValues(op[2]),
    });
  }
  return { rows, editable: true };
}

// Build a filter from rows, always by id so renames don't break cookbooks.
export function buildRule(rows) {
  return rows
    .filter((row) => row.values.length > 0)
    .map((row) => {
      const field = RULE_FIELDS.find((f) => f.key === row.field);
      // Backslashes first, so a value ending in one can't end the quotes early.
      const quoted = row.values.map((v) => `"${String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`).join(", ");
      return `${field.attr} ${row.operator} [${quoted}]`;
    })
    .join(" AND ");
}

// Convert name-based rows to id-based using the live term lists, so a
// cookbook edited here keeps working when a tag is renamed.
export function rowsToIds(rows, lookups) {
  return rows.map((row) => {
    if (row.identifier !== "name") return row;
    const terms = lookups[row.field] || [];
    const values = row.values.map((value) => terms.find((t) => t.name.toLowerCase() === String(value).toLowerCase())?.id || value);
    return { ...row, identifier: "id", values };
  });
}

// Human summary, with missing references flagged.
export function describeRows(rows, lookups) {
  return rows.map((row) => {
    const field = RULE_FIELDS.find((f) => f.key === row.field);
    const terms = lookups[row.field] || [];
    const values = row.values.map((value) => {
      const term = row.identifier === "name"
        ? terms.find((t) => t.name.toLowerCase() === String(value).toLowerCase())
        : terms.find((t) => t.id === value);
      return term ? { label: term.name, missing: false } : { label: row.identifier === "name" ? String(value) : `Missing ${field.label.toLowerCase()}`, missing: true };
    });
    return {
      field: field.label,
      operator: RULE_OPERATORS.find((o) => o.value === row.operator)?.label || row.operator,
      values,
    };
  });
}
