// How often run lists ask CookDex for runs: quickly while anything is queued
// or running, so a new or finishing job shows up within seconds, and slowly
// otherwise. One cheap /runs call to CookDex; nothing reaches Mealie.
export const ACTIVE_RUNS_MS = 3000;
export const IDLE_RUNS_MS = 30000;

export function runsRefetchInterval(payload) {
  const items = payload?.items || [];
  return items.some((run) => run?.status === "queued" || run?.status === "running") ? ACTIVE_RUNS_MS : IDLE_RUNS_MS;
}
