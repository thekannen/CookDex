import React from "react";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { runKind, runTitle, statusOf } from "./story.mjs";

const ICONS = { succeeded: "check-circle", failed: "x-circle", canceled: "x-circle", running: "loader", queued: "clock" };

/** Recent runs, newest first. Clicking one opens its details. */
export default function ActivityList({ taskTitle, onOpen, limit = 20, filter, emptyText = "Nothing has run yet." }) {
  const runs = useQuery({
    queryKey: ["runs", "history", limit],
    queryFn: () => api(`/runs?limit=${limit}`),
    refetchInterval: (query) => ((query.state.data?.items || []).some((r) => ["queued", "running"].includes(r.status)) ? 3000 : 15000),
  });
  const items = (runs.data?.items || []).filter((run) => !filter || filter(run));

  if (runs.isLoading) return <p className="muted">Loading…</p>;
  if (runs.isError) return <p className="danger-text">Couldn't load activity. {String(runs.error?.message || "")}</p>;
  if (!items.length) return <p className="muted">{emptyText}</p>;

  return (
    <ul className="activity-feed">
      {items.map((run) => {
        const status = statusOf(run);
        return (
          <li key={run.run_id}>
            <button type="button" className="activity-row" onClick={() => onOpen(run.run_id)}>
              <Icon name={ICONS[run.status] || "clock"} className={`activity-icon is-${status.tone}${run.status === "running" ? " spin" : ""}`} />
              <span className="activity-main">
                <span className="activity-title">{runTitle(run, taskTitle)}</span>
                <span className="muted tiny">
                  {runKind(run)}
                  {run.status === "failed" || run.status === "canceled" ? ` · ${status.label.toLowerCase()}` : ""}
                </span>
              </span>
              <span className="muted tiny activity-when">
                {run.created_at ? formatDistanceToNow(new Date(run.created_at), { addSuffix: true }) : ""}
              </span>
              <Icon name="chevron" className="activity-chevron" />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
