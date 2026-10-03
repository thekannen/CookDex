// Wording for staged Organize changes. Pure, so it can be tested in Node.


export function describeChange(change, { short = false } = {}) {
  if (change.kind === "cookbooks") {
    const name = change.to?.name || change.name;
    if (change.op === "create") return short ? "New" : `Create cookbook “${name}”`;
    if (change.op === "update") {
      if (short) return name !== change.name ? `→ ${name}` : "Edited";
      return name !== change.name ? `Update cookbook “${change.name}” (renamed to “${name}”)` : `Update cookbook “${name}”`;
    }
    if (change.op === "delete") return short ? "Delete" : `Delete cookbook “${change.name}”`;
  }
  const noun = { tags: "tag", categories: "category", tools: "tool", labels: "label", foods: "food", units: "unit" }[change.kind];
  if (noun && (change.op === "create" || change.op === "update")) {
    const name = change.to?.name || change.name;
    if (change.op === "create") return short ? "New" : `Create ${noun} “${name}”`;
    if (name !== change.name) return short ? `→ ${name}` : `Rename ${noun} “${change.name}” to “${name}”`;
    if (noun === "label") return short ? "Recolored" : `Recolor label “${name}”`;
    return short ? "Edited" : `Edit ${noun} “${name}”`;
  }
  if (change.op === "rename") return short ? `→ ${change.to}` : `Rename “${change.name}” to “${change.to}”`;
  if (change.op === "merge") return short ? `Merge into “${change.target_name}”` : `Merge “${change.name}” into “${change.target_name}”`;
  if (change.op === "delete") return short ? "Delete" : `Delete “${change.name}”`;
  return String(change.op);
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export function stagedSummary(changes) {
  const counts = { rename: 0, merge: 0, delete: 0, create: 0, update: 0 };
  for (const change of changes) counts[change.op] = (counts[change.op] || 0) + 1;
  const parts = [];
  if (counts.merge) parts.push(plural(counts.merge, "merge"));
  if (counts.rename) parts.push(plural(counts.rename, "rename"));
  if (counts.delete) parts.push(plural(counts.delete, "delete"));
  if (counts.create) parts.push(`${counts.create} new`);
  if (counts.update) parts.push(plural(counts.update, "edit"));
  return `${plural(changes.length, "change")} staged: ${parts.join(", ")}`;
}

// Group for the confirmation dialog, e.g. [["Tags: merges", [...]], ...].
export function groupChanges(changes) {
  const order = ["merge", "rename", "create", "update", "delete"];
  const titles = { merge: "merges", rename: "renames", create: "new", update: "edits", delete: "deletions" };
  const groups = new Map();
  for (const change of [...changes].sort((a, b) => order.indexOf(a.op) - order.indexOf(b.op))) {
    const kind = change.kind.charAt(0).toUpperCase() + change.kind.slice(1);
    const key = `${kind}: ${titles[change.op]}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(change);
  }
  return [...groups.entries()];
}


// A backup protects what a change could lose. Adding something new, or
// removing something no recipe uses, loses nothing, and a backup of a large
// library takes minutes, so those changes skip it.
export function needsBackup(changes) {
  return changes.some((change) => !(change.op === "create" || (change.op === "delete" && change.unused)));
}

export function dependencyProblem(changes) {
  const removed = new Set(changes.filter((c) => ["merge", "delete"].includes(c.op)).map((c) => `${c.kind}:${c.id}`));
  return changes.some((c) => c.op === "merge" && removed.has(`${c.kind}:${c.target_id}`))
    ? "A merge target is also being merged or deleted. Keep the target, or choose another one."
    : "";
}

// Job status includes backup and cookbook failures, which may not have an
// individual taxonomy_change record. Only discard changes confirmed applied.
export function applyOutcome(run, result) {
  const items = (result?.results || []).filter((e) => e.kind === "taxonomy_change").flatMap((e) => e.items || []);
  const applied = items.filter((i) => i.status === "applied");
  const remaining = items.filter((i) => i.status !== "applied");
  const count = applied.length;
  if ((result?.status || run?.status) !== "succeeded") {
    return { applied, tone: "warning", text: `Applying changes ${run?.status === "canceled" ? "was canceled" : "failed"}. ${count} change${count === 1 ? " was" : "s were"} applied. Open Recent activity in Tools for details; unapplied changes are still staged.` };
  }
  if (remaining.length) {
    return { applied, tone: "warning", text: `Applied ${count} of ${items.length} changes. ${remaining.length} skipped: ${remaining[0].error || "see Recent activity in Tools"}. Unapplied changes are still staged.` };
  }
  if (!items.length) {
    return { applied, tone: "warning", text: "No changes were confirmed applied. Your changes are still staged. Check Recent activity in Tools before retrying." };
  }
  return { applied, tone: "success", text: `Applied ${count} change${count === 1 ? "" : "s"} to Mealie.` };
}
