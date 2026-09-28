// How the Settings page groups CookDex's settings: by what someone is setting
// up, not by the variables behind it.

export const SECTIONS = [
  {
    id: "mealie",
    groups: ["Connection"],
    title: "Mealie",
    icon: "link",
    blurb: "Where your Mealie is, and the token CookDex signs in with. Everything else builds on this.",
  },
  {
    id: "ai",
    groups: ["AI"],
    title: "AI helper",
    icon: "wand",
    blurb: "Optional. Suggests categories, tags and tools for recipes the rules can't place.",
  },
  {
    id: "database",
    groups: ["Direct DB"],
    title: "Faster database access",
    icon: "database",
    blurb:
      "Optional. Every job works through Mealie's API. On a big library, a database connection makes the heavy ones fast: saving tags on 10,000 recipes takes seconds instead of about 11 minutes. Jobs use it on their own once it's here, and fall back to the API if it can't be reached.",
  },
  {
    id: "sources",
    groups: ["Dredger"],
    title: "Recipe sources",
    icon: "globe",
    blurb: "How Discover reads the sites you add under Recipe Sources.",
  },
  {
    id: "runs",
    groups: ["Updates", "Runner"],
    title: "Updates and runs",
    icon: "clock",
    blurb: "Update checks, and how long a job may run before it's stopped.",
  },
];

const SECTION_BY_GROUP = new Map(SECTIONS.flatMap((section) => section.groups.map((group) => [group, section.id])));

export function sectionOf(group) {
  return SECTION_BY_GROUP.get(String(group || "")) || null;
}

const PROVIDER_NAMES = { chatgpt: "OpenAI", anthropic: "Anthropic", ollama: "Ollama" };

function isSet(specs, key) {
  return Boolean(specs?.[key]?.has_value);
}

/** A short status for a section's header: {text, tone} where tone is ok, warn or "". */
export function sectionStatus(id, specs, draft = {}) {
  if (id === "mealie") {
    return isSet(specs, "MEALIE_URL") && isSet(specs, "MEALIE_API_KEY")
      ? { text: "Set up", tone: "ok" }
      : { text: "Needs setup", tone: "warn" };
  }
  if (id === "ai") {
    const raw = String(draft.CATEGORIZER_PROVIDER ?? specs?.CATEGORIZER_PROVIDER?.value ?? "").trim().toLowerCase();
    if (raw === "none" || raw === "off") return { text: "Off", tone: "" };
    const provider = PROVIDER_NAMES[raw] ? raw : "chatgpt";
    const ready = provider === "ollama" ? isSet(specs, "OLLAMA_URL") : isSet(specs, provider === "anthropic" ? "ANTHROPIC_API_KEY" : "OPENAI_API_KEY");
    if (ready) return { text: PROVIDER_NAMES[provider], tone: "ok" };
    // AI is optional: only nag when someone actually picked a provider.
    const chosen = draft.CATEGORIZER_PROVIDER !== undefined && draft.CATEGORIZER_PROVIDER !== specs?.CATEGORIZER_PROVIDER?.value
      ? true
      : !["default", "unset", ""].includes(String(specs?.CATEGORIZER_PROVIDER?.source || ""));
    return chosen ? { text: `${PROVIDER_NAMES[provider]}, needs a key`, tone: "warn" } : { text: "Not set up", tone: "" };
  }
  if (id === "database") {
    return isSet(specs, "MEALIE_DB_URL") ? { text: "Set up", tone: "ok" } : { text: "Not used", tone: "" };
  }
  return { text: "", tone: "" };
}

/** Where a value comes from, when that's worth saying; "" otherwise. */
export function sourceNote(item) {
  const source = String(item?.source || "");
  if (source === "ui_secret_invalid") return "The saved value can't be read any more. Enter it again.";
  if (source === "environment") return "Set in your compose file. Save it here to manage it from CookDex.";
  if (item?.environment_too) return "Your compose file sets this too; the value here is the one used. You can delete it from the compose file.";
  return "";
}
