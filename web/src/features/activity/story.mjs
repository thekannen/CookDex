// Turns a run and the summaries its job reported (GET /runs/{id}/result) into
// something anyone can read: one sentence, a few numbers, and what went wrong.
// Pure functions, so they can be tested without a browser.

const fmt = (value) => (typeof value === "number" ? value.toLocaleString("en-US") : String(value));
const num = (value) => {
  const n = Number(String(value ?? "").replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
};
const plural = (count, one, many) => `${fmt(count)} ${count === 1 ? one : many}`;

export function isPreview(run) {
  const options = run?.options || {};
  if (options.workflow) return options.workflow.mode !== "apply";
  if (!("dry_run" in options)) return false;
  return options.dry_run !== false && !options.apply_cleanups;
}

const STATUS = {
  queued: { label: "Waiting to start", tone: "neutral" },
  running: { label: "Running", tone: "running" },
  succeeded: { label: "Finished", tone: "success" },
  failed: { label: "Didn't finish", tone: "danger" },
  canceled: { label: "Stopped", tone: "neutral" },
};

export function statusOf(run) {
  return STATUS[run?.status] || { label: String(run?.status || "Unknown"), tone: "neutral" };
}

/** What to call a run: its automation's name, or its job's title. */
export function runTitle(run, taskTitle) {
  const workflow = run?.options?.workflow;
  if (run?.task_id === "workflow" && workflow?.name) return workflow.name;
  return taskTitle(run?.task_id);
}

/** "Preview · automatic" style subtitle. */
export function runKind(run) {
  const parts = [];
  if (run?.options && ("dry_run" in run.options || run.options.workflow)) parts.push(isPreview(run) ? "Preview" : "Applied changes");
  parts.push(run?.schedule_id || run?.triggered_by === "scheduler" ? "automatic" : `started by ${run?.triggered_by || "someone"}`);
  const text = parts.join(" · ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function duration(run) {
  if (!run?.started_at) return "";
  const end = run.finished_at ? new Date(run.finished_at) : new Date();
  const seconds = Math.max(0, Math.round((end - new Date(run.started_at)) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

const GAPS = {
  time: "cooking times",
  yield: "servings",
  nutrition: "nutrition",
  categories: "categories",
  tags: "tags",
  tools: "tools",
  ingredients: "linked ingredients",
};

// Keys that describe how a job ran rather than what it found.
const QUIET_KEYS = new Set(["__title__", "Mode", "Dry Run", "Scope", "Language", "Elapsed", "Duration", "Avg Rate", "Nutrition Sample"]);

function stat(label, value, tone) {
  return { label, value: typeof value === "number" ? fmt(value) : String(value), tone };
}

function failedStat(summary, key = "Failed") {
  const failed = num(summary[key]);
  return failed ? [stat("Couldn't be changed", failed, "danger")] : [];
}

// One formatter per job module. Each gets the summary and whether the run was
// a preview, and returns { title, headline, stats }.
const FORMATTERS = {
  recipe_quality_audit: (s) => ({
    title: "Recipe completeness",
    headline: `${fmt(num(s["Gold %"]))}% of ${plural(num(s["Total Recipes"]), "recipe is", "recipes are")} complete${
      s["Top Gap"] ? `. What's most often missing: ${GAPS[s["Top Gap"]] || s["Top Gap"]}` : ""
    }.`,
    stats: [
      stat("Complete", num(s["Gold (5-6/6)"]), "ok"),
      stat("Missing a detail or two", num(s["Silver (3-4/6)"])),
      stat("Missing a lot", num(s["Bronze (0-2/6)"]), num(s["Bronze (0-2/6)"]) ? "warn" : undefined),
    ],
  }),
  audit_taxonomy: (s) => {
    const noCat = num(s["Without Category"]);
    const noTags = num(s["Without Tags"]);
    const unused = num(s["Unused Tags"]) + num(s["Unused Categories"]);
    return {
      title: "Tags and categories",
      headline:
        noCat || noTags
          ? `${plural(noCat, "recipe has", "recipes have")} no category and ${fmt(noTags)} ${noTags === 1 ? "has" : "have"} no tags.`
          : "Every recipe has a category and tags.",
      stats: [
        stat("No category", noCat, noCat ? "warn" : "ok"),
        stat("No tags", noTags, noTags ? "warn" : "ok"),
        stat("Unused tags and categories", unused),
        ...(num(s["Problematic Tags"]) ? [stat("Tags that look wrong", num(s["Problematic Tags"]), "warn")] : []),
      ],
    };
  },
  rule_tagger: (s, preview) => {
    const links = num(s["Total Assignments"]);
    const recipes = num(preview ? s["Recipes to Update"] : s["Recipes Updated"] ?? s["Recipes to Update"]);
    const where = recipes ? ` on ${plural(recipes, "recipe", "recipes")}` : "";
    return {
      title: "Tagging rules",
      headline: !links
        ? "The rules found nothing new to add."
        : preview
          ? `Would add ${plural(links, "tag, category or tool", "tags, categories and tools")}${where}.`
          : `Added ${plural(links, "tag, category or tool", "tags, categories and tools")}${where}.`,
      stats: [stat(preview ? "Would add" : "Added", links, "ok"), ...(recipes ? [stat("Recipes", recipes)] : []), ...failedStat(s)],
    };
  },
  categorizer_core: (s, preview) => {
    const added = num(s["Categories Added"]) + num(s["Tags Added"]) + num(s["Tools Added"]);
    const processed = String(s["Recipes Processed"] || "").split("/")[0];
    return {
      title: "AI suggestions",
      headline: added
        ? `${preview ? "The AI suggested" : "The AI added"} ${fmt(num(s["Categories Added"]))} categories, ${fmt(num(s["Tags Added"]))} tags and ${fmt(num(s["Tools Added"]))} tools${processed ? ` across ${fmt(num(processed))} recipes` : ""}.`
        : "The AI didn't suggest anything new.",
      stats: [
        stat("Categories", num(s["Categories Added"])),
        stat("Tags", num(s["Tags Added"])),
        stat("Tools", num(s["Tools Added"])),
        ...(num(s["Unclassified"]) ? [stat("It couldn't place", num(s["Unclassified"]), "warn")] : []),
        ...failedStat(s, "Update Failures"),
      ],
    };
  },
  recipe_junk_filter: (s, preview) => {
    const found = num(s["Junk Found"]);
    const review = num(s["Review Candidates"]);
    return {
      title: "Pages that aren't recipes",
      headline: preview
        ? found
          ? `Found ${plural(found, "page that isn't a recipe", "pages that aren't recipes")}${review ? `, and ${fmt(review)} more to decide on` : ""}.`
          : review
            ? `${plural(review, "page might not be a recipe", "pages might not be recipes")}; you decide.`
            : "Every page looks like a real recipe."
        : `Removed ${plural(num(s["Deleted"]), "page", "pages")} that weren't recipes.`,
      stats: [stat(preview ? "Not recipes" : "Removed", preview ? found : num(s["Deleted"]), found ? "warn" : "ok"), ...(review ? [stat("Your call", review)] : []), ...failedStat(s)],
    };
  },
  recipe_deduplicator: (s, preview) => ({
    title: "Duplicate recipes",
    headline: preview
      ? num(s["Duplicates Found"]) ? `Found ${plural(num(s["Duplicates Found"]), "duplicate recipe", "duplicate recipes")}.` : "No duplicate recipes."
      : `Removed ${plural(num(s["Deleted"]), "duplicate recipe", "duplicate recipes")}.`,
    stats: [stat(preview ? "Duplicates" : "Removed", preview ? num(s["Duplicates Found"]) : num(s["Deleted"])), ...failedStat(s)],
  }),
  recipe_name_normalizer: (s, preview) => ({
    title: "Recipe names",
    headline: preview
      ? num(s["Candidates"]) ? `${plural(num(s["Candidates"]), "name could", "names could")} be cleaner.` : "Every name looks clean."
      : `Renamed ${plural(num(s["Applied"]), "recipe", "recipes")}.`,
    stats: [stat(preview ? "To clean up" : "Renamed", preview ? num(s["Candidates"]) : num(s["Applied"])), ...failedStat(s)],
  }),
  ingredient_parser: (s, preview) => {
    const parsed = num(s["Parsed"]);
    const review = num(s["Needs Review"]);
    return {
      title: "Ingredients",
      headline: `${preview ? "Could link" : "Linked"} the ingredients of ${plural(parsed, "recipe", "recipes")}${review ? `; ${fmt(review)} need a person to check` : ""}.`,
      stats: [stat(preview ? "Could link" : "Linked", parsed, "ok"), ...(review ? [stat("Need checking", review, "warn")] : [])],
    };
  },
  foods_manager: (s, preview) => mergeStory("Foods", s, preview),
  units_manager: (s, preview) => mergeStory("Units", s, preview),
  taxonomy_duplicates: (s, preview) => {
    const candidates = Object.entries(s)
      .filter(([key]) => key.endsWith("Merge Candidates"))
      .reduce((total, [, value]) => total + num(value), 0);
    return mergeStory("Tags and categories", { ...s, "Merge Candidates": candidates }, preview);
  },
  yield_normalizer: (s, preview) => {
    const gaps = num(s["Yield Gaps"]);
    return {
      title: "Servings",
      headline: preview
        ? gaps ? `Could fill in servings for ${plural(gaps, "recipe", "recipes")}.` : "Every recipe has its servings."
        : `Filled in servings for ${plural(num(s["Applied"]), "recipe", "recipes")}.`,
      stats: [stat(preview ? "Could fill in" : "Filled in", preview ? gaps : num(s["Applied"])), ...failedStat(s)],
    };
  },
  mealie_backup: (s) => ({
    title: "Backup",
    headline: num(s["Created"])
      ? `Made a Mealie backup${num(s["Pruned"]) ? ` and removed ${plural(num(s["Pruned"]), "older one", "older ones")}` : ""}.`
      : `Removed ${plural(num(s["Pruned"]), "older backup", "older backups")}.`,
    stats: [],
  }),
  recipe_dredger: (s, preview) => {
    const found = num(preview ? s["Recipes Found"] : s["Recipes Imported"]);
    return {
      title: "New recipes",
      headline: `${preview ? "Found" : "Imported"} ${plural(found, "new recipe", "new recipes")} from ${plural(num(s["Sites Scanned"]), "source", "sources")}.`,
      stats: [
        stat(preview ? "Found" : "Imported", found, "ok"),
        ...(num(s["Rejected"]) ? [stat("Skipped", num(s["Rejected"]))] : []),
        ...(num(s["Errors"]) ? [stat("Problems", num(s["Errors"]), "danger")] : []),
      ],
    };
  },
  recipe_reimporter: (s, preview) => ({
    title: "Refresh from websites",
    headline: preview
      ? `Could refresh ${plural(num(s["Candidates"]), "recipe", "recipes")} from their websites.`
      : `Refreshed ${plural(num(s["Reimported"]), "recipe", "recipes")} from their websites.`,
    stats: [stat(preview ? "Could refresh" : "Refreshed", preview ? num(s["Candidates"]) : num(s["Reimported"])), ...failedStat(s)],
  }),
  slug_repair: (s, preview) => {
    const mismatches = num(s["Mismatches"]);
    return {
      title: "Recipe web addresses",
      headline: !mismatches
        ? "Every recipe's web address matches its name."
        : preview
          ? `${plural(mismatches, "recipe has", "recipes have")} a web address that doesn't match its name.`
          : `Fixed the web address of ${plural(num(s["Applied"]), "recipe", "recipes")}.`,
      stats: [
        stat(preview ? "To fix" : "Fixed", preview ? mismatches : num(s["Applied"])),
        ...(num(s["Skipped (slug taken)"]) ? [stat("Left alone (address taken)", num(s["Skipped (slug taken)"]))] : []),
        ...failedStat(s),
      ],
    };
  },
  organize_apply: (s) => ({
    title: "Organize changes",
    headline: `Applied ${plural(num(s["Applied"]), "change", "changes")}.`,
    stats: [...failedStat(s)],
  }),
};

function mergeStory(title, s, preview) {
  const candidates = num(s["Merge Candidates"]);
  return {
    title,
    headline: preview
      ? candidates ? `${plural(candidates, "entry could", "entries could")} be merged into another.` : "Nothing to merge."
      : `Merged ${plural(num(s["Applied"]), "entry", "entries")}.`,
    stats: [stat(preview ? "Could merge" : "Merged", preview ? candidates : num(s["Applied"])), ...failedStat(s)],
  };
}

function humanize(key) {
  return key.replace(/_/g, " ");
}

function genericStory(summary) {
  const stats = Object.entries(summary)
    .filter(([key, value]) => !QUIET_KEYS.has(key) && (typeof value === "number" || typeof value === "string") && value !== "")
    .slice(0, 6)
    .map(([key, value]) => stat(humanize(key), value));
  return { title: summary.__title__ || "Result", headline: "", stats };
}

const QUIET = /^(nothing|no duplicate|every |the rules found nothing|the ai didn't)/i;

/** A headline that says there was nothing to do. */
export function isQuiet(headline) {
  return QUIET.test(String(headline || ""));
}

function moduleOf(source) {
  return String(source || "").split(".").pop();
}

/**
 * The readable version of a finished run.
 * Returns { headline, sections: [{ title, headline, stats }] }.
 */
export function runStory(run, results = []) {
  const preview = isPreview(run);
  const sections = [];
  let pipeline = null;
  for (const entry of Array.isArray(results) ? results : []) {
    const summary = entry?.summary;
    if (!summary || typeof summary !== "object") continue;
    const mod = moduleOf(entry.source);
    if (mod === "data_maintenance" || mod === "tag_pipeline" || mod === "workflow_runner") {
      pipeline = summary;
      continue;
    }
    const format = FORMATTERS[mod];
    sections.push(format ? format(summary, preview) : genericStory(summary));
  }

  let headline = sections.find((s) => s.headline)?.headline || "";
  if (sections.length > 1) {
    // Lead with what needs attention; count the rest.
    const loud = sections.filter((s) => s.headline && !isQuiet(s.headline));
    const quiet = sections.filter((s) => s.headline && isQuiet(s.headline)).length;
    headline = loud.map((s) => s.headline).join(" ");
    if (quiet) headline += loud.length ? ` ${plural(quiet, "other check", "other checks")} found nothing to do.` : "Everything looks good.";
  }
  if (pipeline && num(pipeline.Failed)) {
    headline = `${headline} ${plural(num(pipeline.Failed), "step", "steps")} didn't finish.`.trim();
  }
  if (run?.status === "failed" && !headline) headline = "The job stopped before it finished.";
  if (run?.status === "canceled") headline = run.error || "The job was stopped before it finished.";
  if (!headline && run?.status === "succeeded") headline = "Finished.";
  if (preview && run?.status === "succeeded" && sections.length) headline += " Nothing in Mealie has changed yet.";
  return { headline: headline.trim(), sections, preview };
}

// Log lines worth showing to a person, reworded where we know a better way.
const PROBLEM = /^\[(warn|error)\]\s*(.*)$/;

export function logProblems(text, { limit = 8 } = {}) {
  const seen = new Map();
  for (const raw of String(text || "").split(/\r?\n/)) {
    const match = raw.trim().match(PROBLEM);
    if (!match) continue;
    const level = match[1] === "error" ? "error" : "warning";
    const message = match[2].trim();
    if (!message) continue;
    // Group the same message about different recipes ("Couldn't save 'x': 400").
    const key = `${level}:${message.replace(/(^|[\s(])('[^']*'|"[^"]*")/g, "$1…").replace(/\d+/g, "#")}`;
    const item = seen.get(key) || { level, message, count: 0 };
    item.count += 1;
    seen.set(key, item);
  }
  const items = [...seen.values()].sort((a, b) => (a.level === b.level ? b.count - a.count : a.level === "error" ? -1 : 1));
  return { items: items.slice(0, limit), more: Math.max(0, items.length - limit) };
}

/** Progress for a running job: { label, percent, detail } or null. */
export function describeProgress(progress) {
  if (!progress || !progress.total) return progress?.label ? { label: progress.label, percent: null, detail: "" } : null;
  const done = Math.min(num(progress.done), num(progress.total));
  return {
    label: progress.label,
    percent: Math.round((done / num(progress.total)) * 100),
    detail: `${fmt(done)} of ${fmt(num(progress.total))}`,
  };
}
