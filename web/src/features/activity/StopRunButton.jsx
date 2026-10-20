import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";

// Stops one or more running or queued jobs. Asks once first: a job stopped
// part-way keeps whatever it already changed in Mealie.
export default function StopRunButton({ runIds, label = "Stop", what = "this job", onStopped, onError }) {
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  const ids = (runIds || []).filter(Boolean);

  const stop = useMutation({
    mutationFn: async () => {
      // A job can finish between the click and the request; that's not an error.
      const outcomes = await Promise.allSettled(ids.map((id) => api(`/runs/${id}/cancel`, { method: "POST" })));
      const failed = outcomes.find((o) => o.status === "rejected" && !/cannot be canceled/i.test(String(o.reason?.message || o.reason)));
      if (failed) throw failed.reason;
    },
    onSuccess: () => {
      setAsking(false);
      for (const id of ids) queryClient.invalidateQueries({ queryKey: ["run", id] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["library"] });
      queryClient.invalidateQueries({ queryKey: ["discover"] });
      onStopped?.();
    },
    onError: (exc) => {
      setAsking(false);
      onError?.(exc);
    },
  });

  if (!ids.length) return null;

  if (!asking) {
    return (
      <button type="button" className="ghost small" onClick={() => setAsking(true)} disabled={stop.isPending}>
        <Icon name="x-circle" /> {label}
      </button>
    );
  }
  return (
    <span className="stop-run-confirm" role="group" aria-label={`Stop ${what}?`}>
      <span className="muted tiny">Stop {what}? Changes it already made stay.</span>
      <button type="button" className="danger small" onClick={() => stop.mutate()} disabled={stop.isPending}>
        {stop.isPending ? "Stopping…" : "Stop it"}
      </button>
      <button type="button" className="ghost small" onClick={() => setAsking(false)} disabled={stop.isPending}>
        Keep going
      </button>
    </span>
  );
}
