// Helpers for taxonomy import and export. Pure, so they can be tested in Node.

export const SECTIONS = ["categories", "tags", "tools", "labels", "units_aliases", "cookbooks"];

// Combine picked files into one bundle: a bundle's sections are used as they
// are, and a plain list is read by its file name (tags.json -> tags).
export function bundleFiles(files) {
  const bundle = {};
  const problems = [];
  for (const { name, data } of files) {
    if (Array.isArray(data)) {
      const stem = String(name).split("/").pop().replace(/\.json$/i, "");
      if (SECTIONS.includes(stem)) bundle[stem] = [...(bundle[stem] || []), ...data];
      else problems.push(`${name}: name it after a section, like tags.json`);
    } else if (data && typeof data === "object" && SECTIONS.some((s) => s in data)) {
      for (const section of SECTIONS) {
        if (Array.isArray(data[section])) bundle[section] = [...(bundle[section] || []), ...data[section]];
      }
    } else {
      problems.push(`${name}: not a CookDex taxonomy file`);
    }
  }
  return { bundle, problems };
}

export function exportFileName(date = new Date()) {
  return `cookdex-taxonomy-${date.toISOString().slice(0, 10)}.json`;
}

const KIND_LABELS = { tags: "Tags", categories: "Categories", tools: "Tools", labels: "Labels", units: "Units", cookbooks: "Cookbooks" };

// "Tags: 3 new, 12 already there" lines for the import preview.
export function summaryLines(summary) {
  return Object.entries(summary || {}).map(([kind, counts]) => {
    const parts = [];
    if (counts.new) parts.push(`${counts.new} new`);
    if (counts.updated) parts.push(`${counts.updated} to update`);
    if (counts.unchanged) parts.push(`${counts.unchanged} already there`);
    return `${KIND_LABELS[kind] || kind}: ${parts.join(", ") || "nothing"}`;
  });
}
