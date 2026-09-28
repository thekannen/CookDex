import React from "react";
import { useQuery } from "@tanstack/react-query";

import Icon from "./Icon";
import { api } from "../utils.jsx";

// A notice on every page when CookDex can't reach Mealie, so a page showing
// what it last knew isn't mistaken for the current state.
export default function MealieStatus({ isOwner, onOpenSettings }) {
  const status = useQuery({
    queryKey: ["provider-status"],
    queryFn: () => api("/provider/status", { timeout: 20000 }),
    refetchInterval: (query) => (query.state.data && !query.state.data.ok ? 20000 : 60000),
    retry: false,
  });
  const data = status.data;
  if (!data || data.ok || !data.configured) return null;
  return (
    <div className="mealie-status" role="alert">
      <Icon name="alert-triangle" />
      <p>
        <strong>CookDex can't reach Mealie right now.</strong> {data.detail} Pages show what CookDex last saw, and jobs
        will fail until it's back.
      </p>
      <div className="mealie-status-actions">
        <button type="button" className="ghost small" onClick={() => status.refetch()} disabled={status.isFetching}>
          {status.isFetching ? "Checking…" : "Check again"}
        </button>
        {isOwner ? (
          <button type="button" className="ghost small" onClick={onOpenSettings}>Settings</button>
        ) : null}
      </div>
    </div>
  );
}
