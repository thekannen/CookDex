// Turns a run's structured results (GET /runs/{id}/result) into what the
// review UI shows, and turns a person's selections back into an apply plan.
// Pure functions, so they can be tested without a browser.

export const REVIEWABLE_TASKS = new Set(["clean-recipes"]);

const DELETE_GROUP_ORDER = ["junk", "review", "duplicate"];

export const DELETE_GROUP_COPY = {
  junk: {
    title: "Not recipes",
    hint: "No ingredients and no usable steps. Selected by default.",
  },
  review: {
    title: "Your call",
    hint: "These look off, but they have some recipe content. Nothing is removed unless you select it.",
  },
  duplicate: {
    title: "Duplicate recipes",
    hint: "Same source as another recipe. The most complete copy is kept.",
  },
};

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

// Group the recorded items. Later entries for the same slug win, so a
// pipeline that re-reports an item shows its final state.
export function collectItems(results) {
  const deletes = new Map();
  const renames = new Map();
  for (const entry of Array.isArray(results) ? results : []) {
    if (!Array.isArray(entry?.items)) continue;
    for (const item of entry.items) {
      if (!item || !item.slug) continue;
      if (entry.kind === "recipe_delete") deletes.set(item.slug, item);
      if (entry.kind === "recipe_rename") renames.set(item.slug, item);
    }
  }
  const groups = {};
  for (const group of DELETE_GROUP_ORDER) groups[group] = [];
  for (const item of deletes.values()) {
    const group = DELETE_GROUP_ORDER.includes(item.group) ? item.group : "junk";
    groups[group].push(item);
  }
  return { deleteGroups: groups, renames: [...renames.values()] };
}

// Narrow a collection to some groups, e.g. ["junk"] or ["rename"], so a
// Library finding opens only its own items.
export function filterCollected(collected, groups) {
  if (!Array.isArray(groups) || groups.length === 0) return collected;
  const keep = new Set(groups);
  const deleteGroups = {};
  for (const group of DELETE_GROUP_ORDER) {
    deleteGroups[group] = keep.has(group) ? collected.deleteGroups[group] : [];
  }
  return { deleteGroups, renames: keep.has("rename") ? collected.renames : [] };
}

export function hasItems(collected) {
  const { deleteGroups, renames } = collected;
  return renames.length > 0 || DELETE_GROUP_ORDER.some((group) => deleteGroups[group].length > 0);
}

// Items a preview selects before the person changes anything. Review
// candidates start unselected: they need a human decision.
export function defaultSelection(collected) {
  const selected = new Set();
  for (const group of ["junk", "duplicate"]) {
    for (const item of collected.deleteGroups[group]) {
      if (item.status === "planned") selected.add(`delete:${item.slug}`);
    }
  }
  for (const item of collected.renames) {
    // A new name another recipe already has (or will get) needs a decision.
    if (item.status === "planned" && !item.conflict) selected.add(`rename:${item.slug}`);
  }
  return selected;
}

// One plain sentence for the top of the result.
export function describeResult(collected, { preview }) {
  const { deleteGroups, renames } = collected;
  const count = (items, status) => items.filter((item) => !status || item.status === status).length;
  const parts = [];
  if (preview) {
    const junk = count(deleteGroups.junk);
    const review = count(deleteGroups.review);
    const dupes = count(deleteGroups.duplicate);
    if (junk) parts.push(plural(junk, "entry isn't a recipe", "entries aren't recipes"));
    if (review) parts.push(`${review} to decide on`);
    if (dupes) parts.push(plural(dupes, "duplicate", "duplicates"));
    if (renames.length) parts.push(plural(renames.length, "name to clean up", "names to clean up"));
    if (!parts.length) return "Preview found nothing to change.";
    return `Preview found ${joinParts(parts)}. Nothing in Mealie has changed yet.`;
  }
  const removed = DELETE_GROUP_ORDER.reduce((total, group) => total + count(deleteGroups[group], "applied"), 0);
  const renamed = count(renames, "applied");
  const failed =
    DELETE_GROUP_ORDER.reduce((total, group) => total + count(deleteGroups[group], "error"), 0) + count(renames, "error");
  if (removed) parts.push(`removed ${plural(removed, "recipe", "recipes")}`);
  if (renamed) parts.push(`renamed ${plural(renamed, "recipe", "recipes")}`);
  let sentence = parts.length ? `Applied: ${joinParts(parts)}.` : "No changes were applied.";
  if (failed) sentence += ` ${plural(failed, "change", "changes")} failed; see details.`;
  return sentence;
}

function joinParts(parts) {
  if (parts.length <= 1) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

// Build the plan the task applies. Only selected items are included, and a
// rename carries the name the person approved (possibly edited).
export function buildPlan(collected, selected, editedNames = {}) {
  const plan = { dedup: { delete: [] }, junk: { delete: [] }, names: { rename: {} } };
  for (const group of DELETE_GROUP_ORDER) {
    for (const item of collected.deleteGroups[group]) {
      if (!selected.has(`delete:${item.slug}`)) continue;
      const section = group === "duplicate" ? "dedup" : "junk";
      plan[section].delete.push(item.slug);
    }
  }
  for (const item of collected.renames) {
    if (!selected.has(`rename:${item.slug}`)) continue;
    // A recipe removed in the same batch can't also be renamed.
    if (selected.has(`delete:${item.slug}`)) continue;
    const to = String(editedNames[item.slug] ?? item.new_name ?? "").trim();
    if (!to || to === item.old_name) continue;
    plan.names.rename[item.slug] = { from: item.old_name, to };
  }
  return plan;
}

export function planSize(plan) {
  return {
    deletes: plan.dedup.delete.length + plan.junk.delete.length,
    renames: Object.keys(plan.names.rename).length,
  };
}

export function applyLabel(plan) {
  const { deletes, renames } = planSize(plan);
  const parts = [];
  if (deletes) parts.push(`remove ${plural(deletes, "recipe", "recipes")}`);
  if (renames) parts.push(`rename ${plural(renames, "recipe", "recipes")}`);
  if (!parts.length) return "Nothing selected";
  const text = joinParts(parts);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Options for the live run that applies a reviewed preview. The operations
// match what the preview ran, so every approved item is in scope.
export function applyOptions(previewOptions, plan) {
  const base = { ...(previewOptions || {}) };
  delete base.plan;
  return { ...base, dry_run: false, backup_first: base.backup_first !== false, plan };
}
