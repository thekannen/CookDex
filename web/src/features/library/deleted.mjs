// Recently deleted: plain words for the copies CookDex keeps of recipes the
// junk filter deleted. Pure functions, so they can be tested without a browser.

const DAY_MS = 86_400_000;

export function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/** Whole days left before housekeeping removes a copy (0 means today). */
export function daysLeft(item, keepDays, now = Date.now()) {
  const deleted = Date.parse(item?.deleted_at || "");
  if (!Number.isFinite(deleted)) return null;
  return Math.max(0, Math.ceil((deleted + keepDays * DAY_MS - now) / DAY_MS));
}

export function expiryText(item, keepDays, now = Date.now()) {
  const left = daysLeft(item, keepDays, now);
  if (left === null) return "";
  if (left === 0) return "Removed today";
  return left === 1 ? "Kept 1 more day" : `Kept ${left} more days`;
}

/** Who or what deleted it: "by alex", "by a schedule". */
export function deletedBy(item) {
  const who = String(item?.triggered_by || "").trim();
  if (!who) return "";
  if (who === "scheduler") return "by an automation";
  return `by ${who}`;
}

/** "6 ingredients · 4 steps", or "" when the copy has neither. */
export function contentsText(item) {
  const parts = [];
  const ingredients = Number(item?.ingredients) || 0;
  const steps = Number(item?.steps) || 0;
  if (ingredients) parts.push(`${ingredients} ${ingredients === 1 ? "ingredient" : "ingredients"}`);
  if (steps) parts.push(`${steps} ${steps === 1 ? "step" : "steps"}`);
  if (!parts.length) parts.push("No ingredients or steps");
  if (item?.has_image) parts.push("photo");
  return parts.join(" · ");
}

/** Filter by name or reason; the search box's match. */
export function matchesSearch(item, query) {
  const text = String(query || "").trim().toLowerCase();
  if (!text) return true;
  return [item?.name, item?.slug, item?.reason].some((value) => String(value || "").toLowerCase().includes(text));
}

/** What a finished restore run did, from its recipe_restore items. */
export function restoreOutcome(results) {
  const restored = [];
  const failed = [];
  for (const entry of Array.isArray(results) ? results : []) {
    if (entry?.kind !== "recipe_restore" || !Array.isArray(entry.items)) continue;
    for (const item of entry.items) {
      if (item?.status === "applied") restored.push(item);
      else failed.push(item);
    }
  }
  return { restored, failed };
}

export function restoreNotice({ restored, failed }) {
  if (!restored.length && !failed.length) return null;
  if (!failed.length) {
    if (restored.length === 1) {
      const item = restored[0];
      const moved = item.old_slug && item.slug && item.old_slug !== item.slug ? ` Its web address is now ${item.slug}.` : "";
      return { text: `“${item.name}” is back in Mealie.${moved}`, tone: "success" };
    }
    return { text: `${restored.length} recipes are back in Mealie.`, tone: "success" };
  }
  const first = failed[0];
  const reason = first?.error ? ` ${first.error}` : "";
  if (!restored.length) {
    return { text: `Couldn't restore “${first?.name || "the recipe"}”.${reason}`, tone: "warning" };
  }
  return { text: `${restored.length} restored, ${failed.length} couldn't be.${reason}`, tone: "warning" };
}
