// The sidebar shows the main pages. Hidden pages are still routes, reached
// from links in context (Library, Automations, Organize, the Help button).
export const NAV_ITEMS = [
  { id: "library", label: "Library", icon: "home" },
  { id: "organize", label: "Organize", icon: "tag" },
  { id: "discover", label: "Discover", icon: "globe" },
  { id: "automations", label: "Automations", icon: "calendar" },
  { id: "settings", label: "Settings", icon: "settings", ownerOnly: true },
  { id: "tasks", label: "Tasks", icon: "folder", hidden: true },
  { id: "help", label: "Help", icon: "life-buoy", hidden: true },
];

export const PAGE_META = {
  library: {
    title: "Library",
    subtitle: "",
  },
  organize: {
    title: "Organize",
    subtitle: "",
  },
  tasks: {
    title: "Tasks",
    subtitle: "Every CookDex job with all of its options, run history, and logs.",
  },
  settings: {
    title: "Settings",
    subtitle: "Configure Mealie, AI provider, and runtime behavior from one place.",
  },
  discover: {
    title: "Discover",
    subtitle: "",
  },
  automations: {
    title: "Automations",
    subtitle: "",
  },
  "settings/people": {
    title: "People",
    subtitle: "Manage accounts, reset passwords, and keep access secure.",
  },
  help: {
    title: "Help Center",
    subtitle: "Answers to common questions, troubleshooting tips, and reference guides you can read without leaving the app.",
  },
  "help/about": {
    title: "About CookDex",
    subtitle: "CookDex is designed for home server users who want powerful cleanup and organization workflows without command-line complexity.",
  },
};

export const HELP_SETUP_GUIDES = [
  {
    id: "mealie-connection",
    title: "Find your Mealie URL and API Key",
    icon: "link",
    what: "CookDex needs two values to connect to your Mealie server: the API base URL and an API key with write access.",
    steps: [
      "Your Mealie address is the one you use to open Mealie in a browser, for example http://192.168.1.50:9925, or http://mealie:9000 if CookDex and Mealie share a Docker network. CookDex adds /api for you.",
      "Log into Mealie and click your user icon in the top-right corner.",
      "Open your user profile or account settings page.",
      "Find API Tokens and create a new token for CookDex.",
      "Give the token a clear name, such as cookdex, and generate it.",
      "Copy the token immediately \u2014 Mealie only shows it once.",
      "Paste both into CookDex Settings under Connection, then click Test Mealie. It reports the Mealie version and user it connected as.",
    ],
    tip: "If CookDex runs in Docker alongside Mealie, use the Docker service name (for example http://mealie:9000) instead of localhost.",
  },
  {
    id: "openai-api-key",
    title: "Get an OpenAI API Key",
    icon: "wand",
    what: "An OpenAI API key is required if you want to use the AI provider for recipe categorization. This is optional \u2014 rule-based categorization works without it.",
    steps: [
      "Go to platform.openai.com and sign in (or create an account).",
      "Open the API Keys page from the left sidebar.",
      "Click Create new secret key, give it a name, and click Create.",
      "Copy the key immediately \u2014 OpenAI only shows it once.",
      "In CookDex Settings, paste the key into the OpenAI API Key field under the AI group.",
      "Choose an OpenAI model or keep the default.",
      "Click Test OpenAI to verify it works.",
    ],
    tip: "OpenAI billing and quota must be active for live requests. Use dry runs and small batches when trying a new model.",
  },
  {
    id: "anthropic-api-key",
    title: "Get an Anthropic API Key",
    icon: "wand",
    what: "An Anthropic API key lets you use Anthropic models for recipe categorization. This is optional \u2014 rule-based categorization works without any AI provider.",
    steps: [
      "Go to console.anthropic.com and sign in (or create an account).",
      "Open the API Keys page from the left sidebar.",
      "Click Create Key, give it a name, and click Create.",
      "Copy the key immediately \u2014 Anthropic only shows it once.",
      "In CookDex Settings, set AI Provider to Anthropic.",
      "Paste the key into the Anthropic API Key field under the AI group.",
      "Choose an Anthropic model before testing the connection.",
      "Click Test Anthropic to verify it works.",
    ],
    tip: "Anthropic billing and quota must be active for live requests. Rule-based categorization still works without any AI key.",
  },
  {
    id: "direct-db-setup",
    title: "Connect Mealie's Database (Optional)",
    icon: "database",
    what: "Every job works through Mealie's API. On a large library, a database connection makes the heavy jobs (tagging everything, the health check, yield fixes) much faster. Jobs use it on their own once it's set, and fall back to the API if it can't be reached.",
    steps: [
      "Find Mealie's database settings: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_SERVER, POSTGRES_PORT and POSTGRES_DB in Mealie's compose file.",
      "In Settings \u2192 Faster database access, enter them as one connection string: postgresql://USER:PASSWORD@SERVER:PORT/DB. If CookDex and Mealie share a Docker network, SERVER is the Postgres container's name.",
      "Click Test connection. It should report how many recipes it found.",
      "Save.",
    ],
    tip: "If CookDex can't reach the database directly, open Connect over SSH: CookDex signs in to the Mealie machine and connects from there. With an SSH host set, Find it over SSH can read the connection details from Mealie's container for you. The setup script (docker cp cookdex:/app/scripts/setup-db-tunnel.sh /tmp/ && bash /tmp/setup-db-tunnel.sh) creates and installs the SSH key.",
  },
];

export const HELP_FAQ = [
  {
    question: "Can I dry-run before applying changes?",
    icon: "shield",
    answer:
      "Yes. Most tasks default to dry run. Keep Dry Run enabled when trying a new task or option. Only disable it when you are ready to write changes to Mealie.",
  },
  {
    question: "How do I change tags, categories, cookbooks and the rest?",
    icon: "tag",
    answer:
      "Open Organize. It edits tags, categories, tools, cookbooks, labels, foods and units directly in Mealie. Changes are staged until you apply them, and a backup is taken first. Starter sets give you a ready-made list to begin with.",
  },
  {
    question: "Can I import or export my taxonomy?",
    icon: "upload",
    answer:
      "Yes. Organize has Import and Export for a JSON file with the same sections as the files in configs/taxonomy. An import is staged like any other edit, so you can review it before applying.",
  },
  {
    question: "How do permissions work for team members?",
    icon: "users",
    answer:
      "Create separate accounts in Settings, under People. Owners can manage users, settings, and task policies. Editors can run tasks, manage schedules, and use Organize. Use temporary passwords and rotate after onboarding.",
  },
  {
    question: "How do I schedule recurring tasks?",
    icon: "calendar",
    answer:
      "Open Automations and turn on a routine: a nightly Mealie backup, a weekly library check, or weekly imports from Discover. Pick the day and time, and it runs on its own. For any other task, open All tools from the Automations page, pick the task, switch to Schedule, and save.",
  },
  {
    question: "Can I tag recipes without an AI provider?",
    icon: "tag",
    answer:
      "Yes. The tag-categorize task derives matching rules automatically from your taxonomy item names — no LLM or config files needed. Select Method = Rules Only, or use Both to let rules handle the obvious matches and AI fill in the rest. Rules match recipe names, ingredients and steps (for tools).",
  },
  {
    question: "Do I need to connect Mealie's database?",
    icon: "database",
    answer:
      "No. Every job works through Mealie's API. A database connection (Settings \u2192 Faster database access) only makes the heavy jobs faster on large libraries. Jobs use it on their own once it's set, and fall back to the API when it can't be reached.",
  },
];

export const HELP_TROUBLESHOOTING = [
  {
    title: "Connection and Authentication Issues",
    icon: "shield",
    items: [
      "Verify MEALIE_URL and MEALIE_API_KEY are correct in Settings.",
      "Use Test Mealie to confirm the backend can reach Mealie.",
      "If login fails, check that WEB_COOKIE_SECURE matches your protocol (false for HTTP).",
    ],
  },
  {
    title: "Taxonomy Import and Export",
    icon: "upload",
    items: [
      "Import and Export live on the Organize page and use the same sections as the files in configs/taxonomy.",
      "Each section is a JSON array. Objects need at least a \"name\" field.",
      "An import is staged, not applied. Review the staged changes in Organize, then apply them.",
    ],
  },
  {
    title: "Runs, Scheduling, and Logs",
    icon: "play",
    items: [
      "Click any row in the run history table to load its log output.",
      "Cancelled runs stop at the next safe checkpoint, not immediately.",
      "Schedules support interval and once runs. Date/time values are stored and executed in UTC.",
    ],
  },
  {
    title: "Database Connection",
    icon: "database",
    items: [
      "Test connection in Settings \u2192 Faster database access reports the recipe count when it works, or what failed.",
      "Inside Docker, localhost is the CookDex container itself. Use the Postgres container's name on a shared network, or the Mealie machine's address.",
      "For SSH, the key must be mounted into the container (e.g. /app/.ssh/cookdex_mealie); host paths like ~/.ssh aren't visible inside Docker.",
      "For SQLite, mount Mealie's database file into the container and use sqlite:////path/to/mealie.db.",
      "If the database can't be reached, jobs say so in their log and carry on through the API.",
    ],
  },
];

export const HELP_TASK_GUIDES = [
  {
    id: "recipe-dredger",
    title: "Recipe Dredger",
    icon: "globe",
    group: "Data Pipeline",
    what: "Finds and imports recipes from the sources you switch on. Crawls sitemaps, checks each page is a real recipe via its JSON-LD schema, filters by language, and imports only verified recipes into Mealie. The Discover page is the easiest way to use it.",
    steps: [
      "Open Discover and switch on the sources you like. Suggested sources start switched off.",
      "Choose how many new recipes a run may import at most, then click Preview to see what it would bring in.",
      "Click Import now when you're happy. A run stops once it reaches that number, across all sources.",
      "Use Check sources that are on to find sites that can't be reached, and switch them off.",
    ],
    tip: "Schedule the dredger weekly to continuously discover new recipes. The sitemap cache and duplicate precheck ensure it only processes new content each run.",
  },
  {
    id: "data-maintenance",
    title: "Data Maintenance Pipeline",
    icon: "database",
    group: "Data Pipeline",
    what: "Runs the full cleanup pipeline end-to-end in a fixed stage order: dedup \u2192 junk filter \u2192 name normalize \u2192 ingredient parse \u2192 foods and units cleanup \u2192 categorize \u2192 yield normalize \u2192 quality audit \u2192 taxonomy audit. Select specific stages to run a targeted subset.",
    steps: [
      "Run with Dry Run enabled (the default) and review the log \u2014 no data is changed.",
      "Set the AI Provider dropdown if you want to force ChatGPT, Anthropic, or Ollama for this run.",
      "Enable Apply Cleanup Writes to allow deduplication and cleanup stages to write changes, then re-run.",
      "Use Continue on Error to keep remaining stages running even if one fails.",
    ],
    tip: "Schedule data-maintenance monthly with Dry Run on to get an automatic status report with no risk.",
  },
  {
    id: "clean-recipes",
    title: "Clean Recipe Library",
    icon: "trash",
    group: "Actions",
    what: "Three targeted operations in one: URL-based deduplication (removes imported copies of the same recipe, keeping the most complete version), junk filter (removes non-recipe content such as listicles, how-to articles, digest posts, and placeholder instructions), and name normalizer (converts slug-derived names like 'how-to-make-chicken-pasta-recipe' into proper title case).",
    steps: [
      "Toggle off any operation you do not need \u2014 e.g. disable Normalize Names to run only dedup and junk filter.",
      "Run with Dry Run on to preview which recipes would be removed or renamed.",
      "Use the Junk Filter Category dropdown to scan for only one category of junk at a time.",
      "Disable Dry Run and confirm the policy unlock to write changes.",
    ],
    tip: "Run this first after a bulk import. The junk filter is fast and catches most non-recipe content automatically.",
  },
  {
    id: "slug-repair",
    title: "Repair Recipe Slugs",
    icon: "link",
    group: "Actions",
    what: "Finds recipes whose web address (slug) no longer matches their name, usually from renames by older CookDex versions, and fixes them. Older Mealie versions refuse edits to these recipes.",
    steps: [
      "Run with Dry Run on to list the recipes that would change.",
      "Turn Dry Run off to fix them. This works through Mealie's API, or the database when it's connected.",
      "Recipes whose name would take a slug another recipe already has are left alone and listed.",
    ],
    tip: "Current CookDex renames keep slugs in step, so this is mostly a one-time cleanup.",
  },
  {
    id: "ingredient-parse",
    title: "Ingredient Parser",
    icon: "list",
    group: "Actions",
    what: "Parses raw ingredient text (e.g. '2 cups all-purpose flour, sifted') into structured food, unit, and quantity fields in Mealie. Uses an NLP model first; falls back to AI parsing when confidence is below the threshold. Must run before foods and units cleanup stages can operate on structured data.",
    steps: [
      "Run with Dry Run on to see how many ingredients would be parsed.",
      "Lower the Confidence Threshold to accept more NLP results; raise it to push more to the AI fallback.",
      "Disable Dry Run to write results (requires policy unlock).",
      "Run cleanup-duplicates after parsing to merge any new near-duplicate food entries created during parsing.",
    ],
    tip: "Parsing is incremental \u2014 already-parsed ingredients are skipped. Re-run freely after importing new recipes.",
  },
  {
    id: "yield-normalize",
    title: "Yield Normalizer",
    icon: "refresh",
    group: "Actions",
    what: "Repairs missing or inconsistent yield data. If a recipe has a servings count but no yield text it generates one (e.g. '4 servings'). If a recipe has yield text like '8 cookies' it parses out the number and writes it to the numeric servings field.",
    steps: [
      "Run with Dry Run on to see how many recipes would be updated.",
      "Disable Dry Run to apply changes (requires policy unlock). With the database connected, changes are written in one transaction.",
    ],
    tip: "Safe to run after every import. It only changes recipes where yield data is missing or inconsistent.",
  },
  {
    id: "cleanup-duplicates",
    title: "Clean Up Duplicates",
    icon: "copy",
    group: "Actions",
    what: "Merges duplicate food, unit, tag, and category entries that accumulate over time \u2014 for example 'Butter', 'butter', and 'Unsalted Butter' auto-created by Mealie's recipe scraper, or 'Gluten-Free' and 'gluten free' tags. Normalized duplicates are merged into the most-referenced canonical entry.",
    steps: [
      "Run with Dry Run on to preview what would be merged.",
      "Use Target to pick Foods, Units, or Tags & Categories. Tags and categories only merge when names differ by case, spacing, punctuation, accents, '&' vs 'and', or a plural ending, and need Mealie v3.25 or newer.",
      "Disable Dry Run to apply merges (requires policy unlock).",
      "Re-run after ingredient-parse to resolve new duplicates created during parsing.",
    ],
    tip: "A large food library with many variants is normal after bulk importing. Run this after any parsing job.",
  },
  {
    id: "reimport-recipes",
    title: "Re-import Recipes",
    icon: "refresh-cw",
    group: "Actions",
    what: "Re-scrapes recipes from their original source URLs. Content fields are refreshed from the scraper while recipe identity, favorites, and library organization remain intact.",
    steps: [
      "Run with Dry Run enabled to review which recipes are eligible before making changes.",
      "Set Max Recipes for a safe batch size when validating behavior on large libraries.",
      "Use Specific Slugs with a comma-separated list to reimport only targeted recipes.",
      "Disable Dry Run to apply the refresh and then rerun ingredient-parse if you need fresh structured ingredient data.",
    ],
    tip: "Use this after scraper improvements or site-format changes to refresh stale recipe bodies without deleting your library.",
  },
  {
    id: "tag-categorize",
    title: "Tag and Categorize Recipes",
    icon: "tag",
    group: "Organizers",
    what: "Assigns categories, tags, and kitchen tools to recipes. Both mode runs fast rule-matching first then AI to fill gaps. Rules Only works without any AI provider. AI Only skips rules and sends everything to your configured AI provider.",
    steps: [
      "Start with Method = Both (recommended) and Dry Run on to preview what each layer matches.",
      "Rules Only is free and instant \u2014 patterns are derived automatically from your taxonomy item names.",
      "Rules match names and descriptions, ingredients (for cuisines) and steps (for tools). The first run opens each recipe once; later runs only open recipes that changed.",
      "Keep Missing Target Handling set to Skip unless you want rules to create missing taxonomy entries automatically.",
      "Override AI Provider for this run, or leave blank to use your configured default.",
    ],
    tip: "Both mode gives the best coverage: rules handle obvious name matches for free, then AI catches everything else.",
  },
  {
    id: "health-check",
    title: "Health Check",
    icon: "shield",
    group: "Audits",
    what: "Two read-only audits in one. Recipe Quality scores each recipe on completeness: categories, tags, tools, ingredients, cook time, yield, and nutrition coverage. Taxonomy Audit finds unused taxonomy entries, near-duplicate names, and recipes missing categories or tags.",
    steps: [
      "Run with both scopes enabled to get a full library health report \u2014 no changes are ever made.",
      "With the database connected, nutrition coverage is exact instead of a sample estimate.",
      "Review the summary card in the log output for pass/fail counts and top issues.",
      "Use the report as a prioritized action list: fix missing categories and untagged recipes first.",
    ],
    tip: "Schedule health-check monthly as a read-only report. It never writes any data.",
  },
  {
    id: "mealie-backup",
    title: "Mealie Backup",
    icon: "download",
    group: "Data Pipeline",
    what: "Creates a full Mealie backup via the admin API. Optionally deletes older backups this task made, keeping the newest N. Backups you make in Mealie are never deleted. Also available as a pre-step on destructive tasks via the Backup First toggle.",
    steps: [
      "Run with no options to create a single backup.",
      "Set Keep Newest to delete older backups this task made after creating a new one. Backups made in Mealie, and the ones taken before a change, are never counted or deleted.",
      "Enable Prune Only to clean up older backups this task made without creating a new one.",
      "Use the Backup First toggle on destructive tasks to automatically back up before each run. CookDex keeps the newest 10 of those.",
    ],
    tip: "The nightly backup routine in Automations does this for you and keeps the newest 7.",
  },
];

function inferBasePath() {
  const known = "/cookdex";
  if (window.location.pathname.startsWith(known)) {
    return known;
  }
  return "";
}

export const BASE_PATH = inferBasePath();
export const API = `${BASE_PATH}/api/v1`;
