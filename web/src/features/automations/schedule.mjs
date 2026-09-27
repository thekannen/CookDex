// Next local occurrence of a routine's time, as UTC ISO for the server.
// weekday: 0 = Sunday ... 6 = Saturday; omitted for daily routines.

export function nextOccurrence(time, { weekday = null, now = new Date() } = {}) {
  const [hours, minutes] = String(time || "03:00").split(":").map((part) => Number.parseInt(part, 10) || 0);
  const next = new Date(now.getTime());
  next.setSeconds(0, 0);
  next.setHours(hours, minutes);
  if (weekday === null || weekday === undefined) {
    if (next <= now) next.setDate(next.getDate() + 1);
    return next;
  }
  let days = (Number(weekday) - next.getDay() + 7) % 7;
  if (days === 0 && next <= now) days = 7;
  next.setDate(next.getDate() + days);
  return next;
}

export const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function whenLabel(routine) {
  const [h, m] = String(routine.time || "03:00").split(":").map((part) => Number.parseInt(part, 10) || 0);
  const probe = new Date(2000, 0, 1, h, m);
  const time = probe.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return routine.period === "daily" ? `Every day at ${time}` : `Every ${WEEKDAYS[routine.weekday ?? 0]} at ${time}`;
}
