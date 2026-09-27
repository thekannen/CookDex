// Helpers for editing foods and units. Pure, so they can be tested in Node.

export function aliasesToText(aliases) {
  return (aliases || []).join(", ");
}

// "Tbs, T, tbs" -> ["Tbs", "T"]: trimmed, no repeats, and never the name itself.
export function textToAliases(text, name = "") {
  const seen = new Set([String(name).trim().toLowerCase()]);
  const aliases = [];
  for (const part of String(text || "").split(",")) {
    const alias = part.trim();
    const key = alias.toLowerCase();
    if (alias && !seen.has(key)) {
      seen.add(key);
      aliases.push(alias);
    }
  }
  return aliases;
}

const FIELDS = { foods: ["name", "plural_name", "label_id"], units: ["name", "plural_name", "abbreviation"] };

// The staged update for an edit, or null when nothing changed.
export function ingredientEdit(kind, item, to) {
  const changed =
    FIELDS[kind].some((field) => String(to[field] || "") !== String(item[field] || "")) ||
    aliasesToText(to.aliases) !== aliasesToText(item.aliases);
  return changed ? { op: "update", kind, id: item.id, name: item.name, to } : null;
}
