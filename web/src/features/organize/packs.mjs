// Matching starter-pack items against what a library already has. Pure, so it
// can be tested in Node. Mirrors cookdex.taxonomy_duplicates.normalize_name.

export function normalizeName(name) {
  return String(name || "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/['’]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

// The key plus its likely singular forms, so "Salads" matches "Salad".
function keys(name) {
  const key = normalizeName(name);
  const out = new Set([key]);
  const match = key.match(/^(.*?)([a-z]+)$/);
  if (match && match[2].endsWith("s") && !match[2].endsWith("ss")) {
    const [, head, last] = match;
    out.add(head + last.slice(0, -1));
    if (last.endsWith("es")) out.add(head + last.slice(0, -2));
    if (last.endsWith("ies")) out.add(`${head}${last.slice(0, -3)}y`);
  }
  return out;
}

// Each item with state "have" (already in the library), "staged" or "new".
export function packItems(pack, existingNames, stagedNames = []) {
  const have = new Set(existingNames.flatMap((name) => [...keys(name)]));
  const staged = new Set(stagedNames.flatMap((name) => [...keys(name)]));
  return pack.items.map((item) => {
    const itemKeys = [...keys(item.name)];
    const state = itemKeys.some((k) => have.has(k)) ? "have" : itemKeys.some((k) => staged.has(k)) ? "staged" : "new";
    return { ...item, state };
  });
}

// The staged change that creates one pack item.
export function createChange(kind, item) {
  const to = kind === "labels" ? { name: item.name, color: item.color || "#959595" } : { name: item.name };
  return { op: "create", kind, id: `new-${kind}-${normalizeName(item.name).replace(/ /g, "-")}`, name: item.name, to };
}
