// People: roles in plain words, sign-in names, and temporary passwords.

export const ROLES = {
  owner: {
    label: "Owner",
    article: "an",
    short: "Everything, including Settings and People.",
    can: [
      "Everything an editor can do",
      "Change Settings and the Mealie connection",
      "Add and remove people",
      "Approve automations that change Mealie on their own",
    ],
  },
  editor: {
    label: "Editor",
    article: "an",
    short: "Looks after recipes. Can't change settings or people.",
    can: [
      "Use the Library, Organize, Discover, Tools and Automations",
      "Preview any job, and apply changes an owner has approved",
      "Build automations (an owner approves ones that change Mealie)",
    ],
  },
};

/** A valid sign-in name from what someone typed: "Sam Lee" → "sam-lee". */
export function suggestUsername(name) {
  return String(name || "")
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9_.-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

/** A temporary password that meets the server's rules (upper, lower, digit, 14 long). */
export function generatePassword(random = cryptoRandom) {
  const upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
  const lower = "abcdefghijkmnopqrstuvwxyz";
  const digits = "23456789";
  const all = upper + lower + digits;
  const pick = (set) => set[random(set.length)];
  const chars = [pick(upper), pick(lower), pick(digits)];
  while (chars.length < 14) chars.push(pick(all));
  for (let i = chars.length - 1; i > 0; i -= 1) {
    const j = random(i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join("");
}

function cryptoRandom(max) {
  const buf = new Uint32Array(1);
  const limit = Math.floor(0x100000000 / max) * max;
  let value;
  do {
    globalThis.crypto.getRandomValues(buf);
    value = buf[0];
  } while (value >= limit);
  return value % max;
}

/** Where people sign in: this page's address, up to the app's base path. */
export function signInAddress(location = globalThis.location, base = globalThis.document?.querySelector("base")?.getAttribute("href")) {
  if (!location) return "";
  const path = base && base.startsWith("/") ? base.replace(/\/$/, "") : "";
  return `${location.origin}${path}`;
}
