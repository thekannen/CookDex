// The sidebar shows the main pages. Hidden pages are still routes, reached
// from links in context (Library, Automations, Organize, the Help button).
export const NAV_ITEMS = [
  { id: "library", label: "Library", icon: "home" },
  { id: "organize", label: "Organize", icon: "tag" },
  { id: "discover", label: "Discover", icon: "globe" },
  { id: "automations", label: "Automations", icon: "calendar" },
  { id: "tools", label: "Tools", icon: "wrench" },
  { id: "settings", label: "Settings", icon: "settings", ownerOnly: true },
  { id: "tasks", label: "Classic tools", icon: "folder", hidden: true },
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
    title: "Classic tools",
    subtitle: "Every CookDex job with all of its options, schedules and the raw log on one screen.",
  },
  tools: {
    title: "Tools",
    subtitle: "",
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
    subtitle: "Everyone who can sign in to CookDex. It has its own sign-ins, separate from Mealie's.",
  },
  help: {
    title: "Help",
    subtitle: "How CookDex works, what each page and job is for, and what to do when something's wrong.",
  },
  "help/about": {
    title: "About CookDex",
    subtitle: "CookDex is designed for home server users who want powerful cleanup and organization workflows without command-line complexity.",
  },
};

// First steps, in the order people take them.
export const HELP_GETTING_STARTED = [
  "Connect Mealie in Settings: its address and an API token. Test Mealie tells you if it worked.",
  "Scan your library from the Library page. It only looks; nothing changes.",
  "Work through what it found. Every change is shown to you before it happens, and a backup is made first.",
  "No recipes yet? Pick sites you like in Discover and import a few, or add a starter set of tags and categories in Organize.",
  "Turn on an automation, like the nightly backup or the weekly check, so the library stays tidy on its own.",
];

// One guide per place in the app.
export const HELP_PLACES = [
  {
    id: "library",
    title: "Library",
    icon: "home",
    what: "Your library at a glance: a score out of 100 and a list of things worth fixing, like recipes without categories, duplicates or pages that aren't recipes.",
    steps: [
      "Scan again checks everything. It only looks and changes nothing.",
      "Each finding shows real examples and one button to deal with it. Cleanups open a review where you pick what goes.",
      "Recent activity lists what ran lately. Select one to see what it did.",
    ],
  },
  {
    id: "organize",
    title: "Organize",
    icon: "tag",
    what: "Tags, categories, tools, cookbooks, food labels, foods and units, edited directly in Mealie, with recipe counts and suggested merges.",
    steps: [
      "Rename, merge or remove entries. Changes wait in a tray until you apply them together, after a backup.",
      "Starter sets add ready-made lists, like meal types or cuisines, when you're starting out.",
      "Import and Export move the whole list between CookDex installs as one file.",
    ],
  },
  {
    id: "discover",
    title: "Discover",
    icon: "globe",
    what: "New recipes from recipe sites you choose. Nothing is imported until you switch a site on.",
    steps: [
      "Switch on the sites you like, grouped by cuisine.",
      "Choose at most how many recipes an import brings in, then Preview to see what it would find.",
      "Import now when you're happy, or turn on the weekly import automation.",
    ],
  },
  {
    id: "automations",
    title: "Automations",
    icon: "calendar",
    what: "Jobs strung together that run on their own: every day, every week, every few hours, once, or only when you start them.",
    steps: [
      "Turn on a ready-made one as it is, or open it to change what it does.",
      "New automation: name it, pick when it runs, choose Preview (you review each run) or Apply changes, and add steps. Each step is a job with its own settings.",
      "An automation that changes Mealie on its own needs an owner's approval once. Preview now runs it without changing anything.",
    ],
  },
  {
    id: "tools",
    title: "Tools",
    icon: "wrench",
    what: "Every job CookDex can do, one at a time: clean-ups, tagging, linking ingredients, imports, checks and backups.",
    steps: [
      "Open a job to see what it does and the choices that matter. The rest are under More options.",
      "Preview shows what would change and changes nothing. Apply it from the result, or choose Apply now.",
      "Run automatically turns the job into an automation.",
    ],
  },
  {
    id: "settings",
    title: "Settings and People",
    icon: "settings",
    what: "How CookDex reaches Mealie and the helpers it can use, and who can sign in. Only owners see these.",
    steps: [
      "Mealie: the address and API token. AI helper: optional, for suggestions the rules miss. Faster database access: optional, for big libraries.",
      "People: add someone and CookDex shows the sign-in details to send them. Owners can do everything; editors look after recipes.",
    ],
  },
];

export const HELP_SETUP_GUIDES = [
  {
    id: "mealie-connection",
    title: "Connect Mealie",
    icon: "link",
    what: "CookDex needs two things from Mealie: the address you open it at, and an API token.",
    steps: [
      "The address is the one you use in a browser, like http://192.168.1.50:9925. If CookDex and Mealie run in Docker on the same network, use Mealie's container name, like http://mealie:9000. CookDex adds /api for you.",
      "In Mealie, open your profile (top right), then API Tokens, and create one called cookdex.",
      "Copy it straight away: Mealie shows it only once.",
      "Paste both into Settings \u2192 Mealie and click Test Mealie. It says which Mealie version and user it reached.",
    ],
    tip: "Inside Docker, localhost means the CookDex container itself, not your server. Use the server's address or Mealie's container name instead.",
  },
  {
    id: "openai-api-key",
    title: "Use OpenAI for suggestions (optional)",
    icon: "wand",
    what: "An AI helper suggests categories, tags and tools for recipes the rules can't place. Rules work without it.",
    steps: [
      "Sign in at platform.openai.com and open API keys.",
      "Create a key and copy it: OpenAI shows it only once.",
      "In Settings \u2192 AI helper, pick OpenAI, paste the key, and click Test OpenAI.",
    ],
    tip: "OpenAI charges per use. In Tools, Tag and categorize can try the AI on a few recipes first.",
  },
  {
    id: "anthropic-api-key",
    title: "Use Anthropic for suggestions (optional)",
    icon: "wand",
    what: "The same as OpenAI, with Anthropic's models.",
    steps: [
      "Sign in at console.anthropic.com and open API Keys.",
      "Create a key and copy it: Anthropic shows it only once.",
      "In Settings \u2192 AI helper, pick Anthropic, paste the key, choose a model and click Test Anthropic.",
    ],
    tip: "Anthropic charges per use; billing has to be set up first.",
  },
  {
    id: "direct-db-setup",
    title: "Connect Mealie's database (optional)",
    icon: "database",
    what: "Every job works through Mealie's API. On a large library, a database connection makes the heavy jobs much faster. Jobs use it on their own once it's set, and fall back to the API if it can't be reached.",
    steps: [
      "Find Mealie's database settings in its compose file: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_SERVER, POSTGRES_PORT and POSTGRES_DB.",
      "In Settings \u2192 Faster database access, enter them as one line: postgresql://USER:PASSWORD@SERVER:PORT/DB.",
      "Click Test connection. It should say how many recipes it found. Then save.",
    ],
    tip: "If CookDex can't reach the database directly, open Connect over SSH. With an SSH host set, Find it over SSH reads the details from Mealie's container for you.",
  },
];

export const HELP_FAQ = [
  {
    question: "Can I see what a job will do before it changes anything?",
    icon: "shield",
    answer:
      "Yes. In Tools, jobs that change Mealie start with Preview, which changes nothing and shows what would change. Apply it from the result when you're happy. Automations can be set to Preview too, so each run waits for you to review it.",
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
      "Add people in Settings, under People. CookDex makes a temporary password and shows the sign-in details to send; they choose their own password when they first sign in. Owners can do everything, including Settings, People and approving automations that change Mealie. Editors use the Library, Organize, Discover, Tools and Automations, and can apply changes an owner has approved.",
  },
  {
    question: "How do I make jobs run on their own?",
    icon: "calendar",
    answer:
      "Open Automations. Turn on a ready-made one (nightly backup, weekly check, weekly organizing, weekly import) or choose New automation: pick when it runs, whether it previews or applies changes, and add steps, each a job with its own settings. For a single job, open it in Tools and choose Run automatically.",
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
    title: "Can't reach Mealie",
    icon: "link",
    items: [
      "Open Settings \u2192 Mealie and click Test Mealie. It says what went wrong.",
      "Inside Docker, localhost is the CookDex container. Use your server's address or Mealie's container name.",
      "A token Mealie rejects: create a new one in Mealie (profile \u2192 API Tokens) and paste it in.",
    ],
  },
  {
    title: "Can't sign in to CookDex",
    icon: "lock",
    items: [
      "Ask an owner for a new password: Settings \u2192 People \u2192 New password.",
      "Sign-in works but doesn't stick over plain http:// ? Set WEB_COOKIE_SECURE=false in the compose file.",
    ],
  },
  {
    title: "A job didn't finish",
    icon: "play",
    items: [
      "Open it from Recent activity, Tools or Automations. The details say what happened in plain words, and Technical details has the full log.",
      "Stopping a job takes effect at the next safe point, not instantly.",
      "An automation that changes Mealie and wasn't approved is skipped, with a note saying so. An owner can approve it on the Automations page.",
    ],
  },
  {
    title: "Moving your tags and categories",
    icon: "upload",
    items: [
      "Organize has Import and Export for the whole list as one file.",
      "An import is staged, not applied. Review it in Organize, then apply.",
    ],
  },
  {
    title: "Database connection",
    icon: "database",
    items: [
      "Test connection in Settings \u2192 Faster database access reports the recipe count when it works, or what failed.",
      "For SSH, the key must be mounted into the container (like /app/.ssh/cookdex_mealie); host paths like ~/.ssh aren't visible inside Docker.",
      "If the database can't be reached, jobs say so and carry on through the API.",
    ],
  },
];

// One guide per job in Tools, grouped the same way (see features/tools/catalog.mjs).
export const HELP_TASK_GUIDES = [
  {
    id: "clean-recipes",
    group: "Tidy up recipes",
    icon: "trash",
    title: "Clean up the recipe list",
    what: "Finds pages that aren't recipes (no ingredients and no usable steps), recipes imported twice from the same page, and names like 'how-to-make-chicken-pasta-recipe'.",
    steps: [
      "Preview it. A review opens with what it found: pages that aren't recipes are picked for you, borderline ones are yours to decide, and new names can be edited.",
      "Apply what you picked. Only those change, after a backup.",
    ],
    tip: "The Library runs this preview for you when it scans, so its findings open the same review.",
  },
  {
    id: "slug-repair",
    group: "Tidy up recipes",
    icon: "link",
    title: "Fix recipe web addresses",
    what: "Finds recipes whose web address (slug) no longer matches their name, usually after renames by older versions, and fixes them. Older Mealie versions refuse edits to these recipes.",
    steps: [
      "Preview it to see which recipes would change.",
      "Apply it. Recipes whose address another recipe already has are left alone and listed.",
    ],
  },
  {
    id: "tag-categorize",
    group: "Organize",
    icon: "tag",
    title: "Tag and categorize",
    what: "Adds categories, tags and kitchen tools to recipes. Rules are made from the names you already have and match recipe names, ingredients (for cuisines) and steps (for tools). An AI helper, if set up, fills in what the rules miss.",
    steps: [
      "Pick how: Rules only (free and instant), Rules then AI, or AI only.",
      "Preview it to see how many recipes would get what. Try the AI on a few recipes first if you like.",
      "Apply it from the preview.",
    ],
    tip: "No tags or categories yet? Add a starter set in Organize first; the rules need names to work from.",
  },
  {
    id: "ingredient-parse",
    group: "Organize",
    icon: "list",
    title: "Link ingredients",
    what: "Reads ingredient lines like '2 cups flour' and links them to foods and units, so shopping lists, search and nutrition work. Lines it isn't sure about can go to Mealie's own AI parser, if that's on in Mealie.",
    steps: [
      "Preview it, on a limited number of recipes if you like.",
      "Apply it. Recipes already linked are skipped, so it's safe to run again after importing.",
    ],
    tip: "Run Merge duplicate foods and units afterwards to tidy up near-duplicates it may create.",
  },
  {
    id: "cleanup-duplicates",
    group: "Organize",
    icon: "copy",
    title: "Merge duplicate foods, units and tags",
    what: "Merges near-identical entries, like 'Garlic' and 'garlic', 'tsp' and 'teaspoon', or 'Gluten-Free' and 'gluten free', into the most-used one. Recipes keep working.",
    steps: [
      "Pick what to merge: foods and units, or tags and categories.",
      "Preview it, then apply.",
    ],
    tip: "Merging tags and categories needs Mealie v3.25 or newer.",
  },
  {
    id: "yield-normalize",
    group: "Organize",
    icon: "refresh",
    title: "Fill in servings",
    what: "Fills in missing servings from a recipe's yield text ('8 cookies'), and yield text from servings.",
    steps: ["Preview it to see how many recipes would change, then apply."],
  },
  {
    id: "recipe-dredger",
    group: "Bring in recipes",
    icon: "globe",
    title: "Import from your sources",
    what: "Looks through the recipe sites switched on in Discover, checks each page is a real recipe in your language, and imports new ones.",
    steps: [
      "Switch sites on in Discover and pick at most how many to import.",
      "Preview it to see what it would find, then import.",
    ],
    tip: "The weekly import automation does this for you.",
  },
  {
    id: "reimport-recipes",
    group: "Bring in recipes",
    icon: "download",
    title: "Refresh recipes from their websites",
    what: "Re-reads recipes from the sites they came from. Favorites, tags, categories and cookbooks stay; the name, ingredients, steps, times and nutrition are replaced, so edits you made to those are lost.",
    steps: [
      "Preview it, on a few recipes first.",
      "Apply it, then run Link ingredients for the refreshed ones.",
    ],
  },
  {
    id: "health-check",
    group: "Check and keep safe",
    icon: "shield",
    title: "Check library health",
    what: "Scores how complete your recipes are (categories, tags, tools, ingredients, times, servings, nutrition) and finds recipes without categories or tags and unused tags. Only looks.",
    steps: ["Run it. The result says what's most often missing."],
    tip: "The weekly check automation includes it.",
  },
  {
    id: "mealie-backup",
    group: "Check and keep safe",
    icon: "save",
    title: "Back up Mealie",
    what: "Makes a full Mealie backup you can restore from Mealie's admin settings. It can also remove older backups CookDex made; backups you made in Mealie are never deleted.",
    steps: ["Run it any time. Jobs that change Mealie also back up first on their own; CookDex keeps the newest 10 of those."],
    tip: "The nightly backup automation keeps the newest 7.",
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
