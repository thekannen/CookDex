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
  "library/deleted": {
    title: "Recently deleted",
    subtitle: "",
  },
  "settings/people": {
    title: "People",
    subtitle: "Everyone who can sign in to CookDex. It has its own sign-ins, separate from Mealie's.",
  },
  help: {
    title: "Help",
    subtitle: "Where to find the CookDex docs, the first steps, and a report to send when something's wrong.",
  },
  "help/about": {
    title: "About CookDex",
    subtitle: "CookDex is designed for home server users who want powerful cleanup and organization workflows without command-line complexity.",
  },
};

// The user docs live on the CookDex site; Help keeps a short intro per topic
// and links there, so there's one copy to keep up to date.
export const DOCS_URL = "https://knownframe.com/cookdex/docs/";
export const PRIVACY_POLICY_URL = "https://knownframe.com/privacy/cookdex/";

// First steps, in the order people take them. Kept in the app so a first run
// works without internet access; the full guide is on the docs site.
export const HELP_GETTING_STARTED = [
  "Connect Mealie in Settings: its address and an API token. Test Mealie tells you if it worked.",
  "Scan your library from the Library page. It only looks; nothing changes.",
  "Work through what it found. Every change is shown to you before it happens, and a backup is made first.",
  "Turn on an automation, like the nightly backup or the weekly check, so the library stays tidy on its own.",
];

// One card per topic: what it covers, and where the docs say more.
export const HELP_TOPICS = [
  {
    id: "places",
    icon: "home",
    title: "The places in CookDex",
    intro: "What Library, Organize, Discover, Automations, Tools and Settings are for.",
    links: [{ label: "Where things are", url: `${DOCS_URL}getting-started/#where-things-are` }],
  },
  {
    id: "connecting",
    icon: "link",
    title: "Connecting things",
    intro: "Installing CookDex, connecting Mealie and an AI helper, and the optional database connection for big libraries.",
    links: [
      { label: "Install", url: `${DOCS_URL}install/` },
      { label: "Connect Mealie", url: `${DOCS_URL}getting-started/#sign-in-and-connect-mealie` },
      { label: "Database connection", url: `${DOCS_URL}database-connection/` },
    ],
  },
  {
    id: "jobs",
    icon: "wrench",
    title: "Jobs in Tools",
    intro: "What each job does and its options. Each job in Tools also links to its own section.",
    links: [
      { label: "All jobs", url: `${DOCS_URL}tasks/` },
      { label: "Data maintenance", url: `${DOCS_URL}tasks/data-maintenance/` },
      { label: "Backups and cleanup", url: `${DOCS_URL}tasks/backups-and-cleanup/` },
      { label: "Tags and categories", url: `${DOCS_URL}tasks/taxonomy/` },
      { label: "Recipe Dredger", url: `${DOCS_URL}recipe-dredger/` },
    ],
  },
  {
    id: "safety",
    icon: "shield",
    title: "Scheduling and safety",
    intro: "Running jobs on a schedule, and how previews, approvals and backups keep Mealie safe.",
    links: [
      { label: "Scheduling", url: `${DOCS_URL}scheduling/` },
      { label: "Safety policies", url: `${DOCS_URL}safety-policies/` },
    ],
  },
  {
    id: "privacy",
    icon: "lock",
    title: "Privacy",
    intro: "What CookDex stores, what it connects to, and how to turn off the update check.",
    links: [
      { label: "Privacy and safety", url: `${DOCS_URL}privacy-and-safety/` },
      { label: "Privacy policy", url: PRIVACY_POLICY_URL },
    ],
  },
];

export const HELP_TROUBLESHOOTING_URL = `${DOCS_URL}troubleshooting/`;

// Where each job in Tools is described in the docs (one entry per task).
const TASK_DOC_PAGES = {
  "clean-recipes": "tasks/data-maintenance/#clean-recipes",
  "slug-repair": "tasks/data-maintenance/#slug-repair",
  "ingredient-parse": "tasks/data-maintenance/#ingredient-parse",
  "yield-normalize": "tasks/data-maintenance/#yield-normalize",
  "reimport-recipes": "tasks/data-maintenance/#reimport-recipes",
  "health-check": "tasks/data-maintenance/#health-check",
  "tag-categorize": "tasks/taxonomy/#tag-categorize",
  "cleanup-duplicates": "tasks/backups-and-cleanup/#cleanup-duplicates",
  "mealie-backup": "tasks/backups-and-cleanup/#mealie-backup",
  "recipe-dredger": "recipe-dredger/",
};

export function taskDocsUrl(taskId) {
  const page = TASK_DOC_PAGES[taskId];
  return page ? `${DOCS_URL}${page}` : `${DOCS_URL}tasks/`;
}

function inferBasePath() {
  const known = "/cookdex";
  if (window.location.pathname.startsWith(known)) {
    return known;
  }
  return "";
}

export const BASE_PATH = inferBasePath();
export const API = `${BASE_PATH}/api/v1`;
