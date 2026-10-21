import React, { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";

import Icon from "../../components/Icon";
import LoadError from "../../components/LoadError";
import RunSheet from "../activity/RunSheet";
import { api } from "../../utils.jsx";
import {
  contentsText, deletedBy, expiryText, formatBytes, matchesSearch, restoreNotice, restoreOutcome,
} from "./deleted.mjs";

// Recipes the junk filter or the duplicate finder deleted, kept for a while so
// any one can go back.
// Restoring is a quick job; this page follows it and refreshes when it's done.
export default function RecentlyDeleted({ canChange, taskTitle, onConfirm, onNotice, onError }) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [openRun, setOpenRun] = useState(null);
  // Restore runs started here, so their outcome can be announced when they finish.
  const watching = useRef(new Set());

  const list = useQuery({
    queryKey: ["deleted-recipes"],
    queryFn: () => api("/deleted-recipes"),
    refetchInterval: (query) => ((query.state.data?.items || []).some((item) => item.restoring_run_id) ? 2000 : false),
  });
  const items = list.data?.items || [];
  const keepDays = list.data?.keep_days || 30;

  // A watched run that no copy points at any more has finished.
  useEffect(() => {
    if (!list.data) return;
    const active = new Set(items.map((item) => item.restoring_run_id).filter(Boolean));
    for (const runId of [...watching.current]) {
      if (active.has(runId)) continue;
      watching.current.delete(runId);
      api(`/runs/${runId}/result`)
        .then((result) => {
          const notice = restoreNotice(restoreOutcome(result?.results));
          if (notice) onNotice?.(notice.text, { tone: notice.tone });
          queryClient.invalidateQueries({ queryKey: ["runs"] });
        })
        .catch((exc) => onError?.(exc));
    }
  }, [list.data]);

  const restore = useMutation({
    mutationFn: (ids) => api("/deleted-recipes/restore", { method: "POST", body: { ids } }),
    onSuccess: (run) => {
      if (run?.run_id) watching.current.add(run.run_id);
      queryClient.invalidateQueries({ queryKey: ["deleted-recipes"] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: (exc) => onError?.(exc),
  });

  const clear = useMutation({
    mutationFn: (id) => api(`/deleted-recipes/${encodeURIComponent(id)}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["deleted-recipes"] }),
    onError: (exc) => onError?.(exc),
  });

  const shown = useMemo(() => items.filter((item) => matchesSearch(item, search)), [items, search]);

  function askClear(item) {
    onConfirm?.({
      title: "Delete this copy now?",
      message: `“${item.name}” is already gone from Mealie. Deleting CookDex's copy means it can't be restored.`,
      confirmLabel: "Delete now",
      action: () => clear.mutate(item.id),
    });
  }

  if (list.isLoading) {
    return <section className="library"><p className="muted">Loading recently deleted recipes…</p></section>;
  }
  if (list.isError && !list.data) {
    return (
      <section className="library">
        <LoadError what="recently deleted recipes" error={list.error} onRetry={() => list.refetch()} retrying={list.isFetching} />
      </section>
    );
  }

  return (
    <section className="library deleted-page">
      <header className="library-head">
        <div>
          <h2>Recently deleted</h2>
          <p className="muted">
            When the junk filter or the duplicate finder deletes a recipe, CookDex keeps a copy here for {keepDays} {keepDays === 1 ? "day" : "days"}, so you can put it back.
            {items.length ? ` ${items.length} ${items.length === 1 ? "recipe" : "recipes"}, ${formatBytes(list.data?.total_bytes)}.` : ""}
          </p>
        </div>
        {items.length > 6 ? (
          <input
            type="search"
            className="deleted-search"
            placeholder="Find a recipe"
            aria-label="Find a deleted recipe"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        ) : null}
      </header>

      {items.length === 0 ? (
        <div className="library-empty">
          <Icon name="trash" />
          <h2>Nothing here</h2>
          <p className="muted">Recipes the junk filter or the duplicate finder deletes show up here, and stay for {keepDays} days.</p>
        </div>
      ) : (
        <>
          <p className="muted tiny deleted-note">
            A restored recipe comes back with its ingredients, steps, photo, tags and categories. Its web address and id may change.
          </p>
          {shown.length === 0 ? <p className="muted library-quiet">No deleted recipe matches “{search}”.</p> : null}
          <ul className="finding-list deleted-list">
            {shown.map((item) => {
              const busy = Boolean(item.restoring_run_id);
              return (
                <li key={item.id} className="finding deleted-row" data-testid="deleted-row">
                  <span className="finding-count" aria-hidden="true"><Icon name="trash" /></span>
                  <div className="finding-body">
                    <strong>{item.name || item.slug}</strong>
                    <span className="muted">{item.reason}</span>
                    <span className="muted tiny">
                      {[
                        item.deleted_at ? `Deleted ${format(new Date(item.deleted_at), "PP p")}` : "",
                        deletedBy(item),
                        contentsText(item),
                        expiryText(item, keepDays),
                      ].filter(Boolean).join(" · ")}
                      {item.run_id && item.run_in_history ? (
                        <>
                          {" · "}
                          <button type="button" className="link-inline" onClick={() => setOpenRun(item.run_id)}>
                            The run that deleted it
                          </button>
                        </>
                      ) : null}
                    </span>
                  </div>
                  <div className="deleted-actions">
                    {busy ? (
                      <span className="muted tiny" role="status"><Icon name="loader" className="spin" /> Restoring…</span>
                    ) : canChange ? (
                      <>
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => restore.mutate([item.id])}
                          disabled={restore.isPending}
                        >
                          <Icon name="refresh" /> Restore
                        </button>
                        <button type="button" className="ghost danger-text" onClick={() => askClear(item)} disabled={clear.isPending}>
                          Delete now
                        </button>
                      </>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
          {!canChange ? <p className="muted tiny">An owner has to approve live cleanups before you can restore recipes.</p> : null}
        </>
      )}
      <RunSheet
        runId={openRun}
        open={Boolean(openRun)}
        onOpenChange={(open) => { if (!open) setOpenRun(null); }}
        taskTitle={taskTitle}
        onError={onError}
      />
    </section>
  );
}
