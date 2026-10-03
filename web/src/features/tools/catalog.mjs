// The Tools page's view of CookDex's jobs: grouped by what someone wants to
// get done, described in plain words, with the one or two choices most people
// need up front. Every other option a job has stays under "More options".

export const GOALS = [
  { id: "tidy", title: "Tidy up recipes", blurb: "Clear out junk, duplicates and messy names." },
  { id: "organize", title: "Organize", blurb: "Tag, categorize and link ingredients so recipes are easy to find." },
  { id: "bring", title: "Bring in recipes", blurb: "Add new recipes, or refresh ones you have." },
  { id: "safe", title: "Check and keep safe", blurb: "See how the library is doing, and keep backups." },
  { id: "advanced", title: "Other jobs", blurb: "Jobs that don't fit the groups above." },
];

// kind: "changes" jobs preview first and apply after; "check" jobs only look;
// "action" jobs just do their one thing (a backup).
export const JOBS = {
  "clean-recipes": {
    goal: "tidy",
    icon: "trash",
    title: "Clean up the recipe list",
    blurb: "Finds pages that aren't recipes, duplicate recipes and messy names. You pick what goes before anything changes.",
    kind: "changes",
    choices: {
      run_junk: "Pages that aren't recipes",
      run_dedup: "Duplicate recipes",
      run_names: "Messy names",
    },
  },
  "slug-repair": {
    goal: "tidy",
    icon: "link",
    title: "Fix recipe web addresses",
    blurb: "Finds recipes whose web address no longer matches their name, and fixes them.",
    kind: "changes",
  },
  "tag-categorize": {
    goal: "organize",
    icon: "tag",
    title: "Tag and categorize",
    blurb: "Adds categories, tags and kitchen tools to recipes, using rules made from the names you already have, and AI if it's set up.",
    kind: "changes",
    choices: {
      method: {
        label: "How",
        options: { both: "Rules, then AI for the rest", rules: "Rules only (free, instant)", ai: "AI only" },
      },
      fill: {
        label: "AI fills in",
        options: { any: "Anything missing", categories: "Only missing categories", tags: "Only missing tags", tools: "Only missing tools" },
      },
      max_recipes: "Try the AI on at most (recipes)",
    },
  },
  "ingredient-parse": {
    goal: "organize",
    icon: "list",
    title: "Link ingredients",
    blurb: "Reads ingredient lines like \"2 cups flour\" and links them to foods and units, so shopping lists and search work.",
    kind: "changes",
    choices: { max_recipes: "At most (recipes)" },
  },
  "cleanup-duplicates": {
    goal: "organize",
    icon: "copy",
    title: "Merge duplicate foods, units and tags",
    blurb: "Merges near-identical entries, like \"Garlic\" and \"garlic\", or \"tsp\" and \"teaspoon\". Recipes keep working.",
    kind: "changes",
    choices: {
      target: {
        label: "What to merge",
        options: {
          both: "Foods and units",
          foods: "Foods",
          units: "Units",
          taxonomy: "Tags and categories",
          tags: "Tags",
          categories: "Categories",
        },
      },
    },
  },
  "yield-normalize": {
    goal: "organize",
    icon: "refresh",
    title: "Fill in servings",
    blurb: "Fills in missing servings from the recipe's yield text, and the other way round.",
    kind: "changes",
  },
  "recipe-dredger": {
    goal: "bring",
    icon: "globe",
    title: "Import from your sources",
    blurb: "Looks through the recipe sites switched on in Discover and imports new recipes.",
    kind: "changes",
    choices: { max_total: "New recipes per run" },
  },
  "reimport-recipes": {
    goal: "bring",
    icon: "download",
    title: "Refresh recipes from their websites",
    blurb: "Re-reads recipes from the sites they came from. Your favorites, tags and cookbooks stay as they are.",
    kind: "changes",
    choices: { max_recipes: "At most (recipes)" },
  },
  "health-check": {
    goal: "safe",
    icon: "shield",
    title: "Check library health",
    blurb: "Scores how complete your recipes are and finds recipes without categories or tags. Only looks; changes nothing.",
    kind: "check",
  },
  "mealie-backup": {
    goal: "safe",
    icon: "save",
    title: "Back up Mealie",
    blurb: "Makes a full Mealie backup you can restore from Mealie's admin settings.",
    kind: "action",
    choices: { keep: "Keep the newest (backups CookDex made)" },
  },
  "data-maintenance": {
    goal: "advanced",
    icon: "layers",
    title: "Run several jobs in a row",
    blurb: "Runs the cleanup, parsing, merging, tagging and checking jobs you pick, in a sensible order.",
    kind: "changes",
  },
};

// Jobs other pages run for you (Organize applies its own changes), and the
// old several-jobs pipeline, which automations replace: an automation runs the
// jobs you pick, in your order, with settings per step and a schedule.
// Automations and classic Tasks that already use it keep working.
export const HIDDEN_JOBS = new Set(["organize-apply", "data-maintenance"]);

export function jobInfo(task) {
  const known = JOBS[task.task_id];
  if (known) return known;
  return { goal: "advanced", icon: "wrench", title: task.title, blurb: task.description, kind: hasOption(task, "dry_run") ? "changes" : "check" };
}

export function hasOption(task, key) {
  return (task?.options || []).some((option) => option.key === key);
}

/** Option specs split into the curated choices and everything else. */
export function splitOptions(task) {
  const choices = JOBS[task.task_id]?.choices || {};
  const main = [];
  const more = [];
  for (const option of task.options || []) {
    if (["dry_run", "backup_first", "apply_cleanups"].includes(option.key)) continue;
    if (option.hidden) continue;
    const curated = choices[option.key];
    if (curated) {
      const label = typeof curated === "string" ? curated : curated.label;
      const labels = typeof curated === "object" ? curated.options : null;
      main.push({
        ...option,
        label,
        choices: labels && Array.isArray(option.choices)
          ? option.choices.map((choice) => {
              const value = typeof choice === "object" ? choice.value : choice;
              return { value, label: labels[value] || (typeof choice === "object" ? choice.label : choice) };
            })
          : option.choices,
      });
    } else {
      more.push(option);
    }
  }
  const order = Object.keys(choices);
  main.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
  return { main, more };
}

/** Options for a preview (changes nothing) or a real run of a job. */
export function runOptions(task, values, { apply }) {
  const options = {};
  for (const [key, value] of Object.entries(values || {})) {
    if (value === "" || value === null || value === undefined) continue;
    options[key] = value;
  }
  if (hasOption(task, "dry_run")) options.dry_run = !apply;
  if (apply && hasOption(task, "backup_first") && options.backup_first === undefined) options.backup_first = true;
  if (apply && hasOption(task, "apply_cleanups")) options.apply_cleanups = true;
  if (!apply) {
    delete options.backup_first;
    delete options.apply_cleanups;
  }
  return options;
}

/** Group visible jobs by goal, in catalog order. */
export function groupJobs(tasks) {
  const order = Object.keys(JOBS);
  const byGoal = new Map(GOALS.map((goal) => [goal.id, []]));
  for (const task of tasks || []) {
    if (HIDDEN_JOBS.has(task.task_id)) continue;
    const info = jobInfo(task);
    (byGoal.get(info.goal) || byGoal.get("advanced")).push({ task, info });
  }
  for (const list of byGoal.values()) {
    list.sort((a, b) => {
      const ai = order.indexOf(a.task.task_id);
      const bi = order.indexOf(b.task.task_id);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });
  }
  return GOALS.map((goal) => ({ ...goal, jobs: byGoal.get(goal.id) })).filter((goal) => goal.jobs.length > 0);
}

// ── Schedules: "every day at 3 AM", "every Sunday at 8 AM" ──────────────

export const DAY = 86_400;
export const WEEK = 7 * DAY;

/** Describe a schedule the way a person would say it. */
export function describeSchedule(schedule, { weekdayNames = WEEKDAY_NAMES } = {}) {
  const data = schedule?.schedule_data || {};
  if (schedule?.schedule_kind === "once") {
    return data.run_at ? `Once, ${new Date(data.run_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}` : "Once";
  }
  const seconds = Number(data.seconds || 0);
  const start = data.start_at ? new Date(data.start_at) : null;
  const time = start ? start.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
  if (seconds === DAY) return `Every day${time ? ` at ${time}` : ""}`;
  if (seconds === WEEK) return `Every ${start ? weekdayNames[start.getDay()] : "week"}${time ? ` at ${time}` : ""}`;
  if (seconds && seconds % DAY === 0) return `Every ${seconds / DAY} days`;
  if (seconds && seconds % 3600 === 0) return seconds === 3600 ? "Every hour" : `Every ${seconds / 3600} hours`;
  if (seconds && seconds % 60 === 0) return `Every ${seconds / 60} minutes`;
  return seconds ? `Every ${seconds} seconds` : "On a schedule";
}

export const WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
