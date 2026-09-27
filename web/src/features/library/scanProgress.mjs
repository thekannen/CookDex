// Wording for the Library's scan progress. Pure, so it can be tested in Node.

const FINISHED = new Set(["succeeded", "failed", "canceled"]);

function formatCount(n) {
  return Number(n || 0).toLocaleString("en-US");
}

// One scan step (a run) as { state, detail, percent }.
export function describeStep(step) {
  if (step.status === "succeeded") return { state: "done", detail: "Done", percent: 100 };
  if (step.status === "failed" || step.status === "canceled") return { state: "failed", detail: "Didn't finish", percent: null };
  if (step.status === "queued") return { state: "waiting", detail: "Waiting", percent: null };
  const progress = step.progress;
  if (!progress || !progress.total) return { state: "running", detail: "Starting…", percent: null };
  const percent = Math.min(100, Math.round((progress.done / progress.total) * 100));
  return {
    state: "running",
    detail: `${progress.label} · ${formatCount(progress.done)} of ${formatCount(progress.total)}`,
    percent,
  };
}

// "Step 2 of 3": the first step that isn't finished.
export function stepHeading(steps) {
  const total = steps.length;
  const current = steps.findIndex((step) => !FINISHED.has(step.status));
  return current === -1 ? `Finishing up` : `Step ${current + 1} of ${total}`;
}
