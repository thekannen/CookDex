// Wording for staged Organize changes. Pure, so it can be tested in Node.


export function describeChange(change, { short = false } = {}) {
  if (change.op === "rename") return short ? `→ ${change.to}` : `Rename “${change.name}” to “${change.to}”`;
  if (change.op === "merge") return short ? `Merge into “${change.target_name}”` : `Merge “${change.name}” into “${change.target_name}”`;
  if (change.op === "delete") return short ? "Delete" : `Delete “${change.name}”`;
  return String(change.op);
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export function stagedSummary(changes) {
  const counts = { rename: 0, merge: 0, delete: 0 };
  for (const change of changes) counts[change.op] = (counts[change.op] || 0) + 1;
  const parts = [];
  if (counts.merge) parts.push(plural(counts.merge, "merge"));
  if (counts.rename) parts.push(plural(counts.rename, "rename"));
  if (counts.delete) parts.push(plural(counts.delete, "delete"));
  return `${plural(changes.length, "change")} staged: ${parts.join(", ")}`;
}

// Group for the confirmation dialog, e.g. [["Tags: merges", [...]], ...].
export function groupChanges(changes) {
  const order = ["merge", "rename", "delete"];
  const titles = { merge: "merges", rename: "renames", delete: "deletions" };
  const groups = new Map();
  for (const change of [...changes].sort((a, b) => order.indexOf(a.op) - order.indexOf(b.op))) {
    const kind = change.kind.charAt(0).toUpperCase() + change.kind.slice(1);
    const key = `${kind}: ${titles[change.op]}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(change);
  }
  return [...groups.entries()];
}

