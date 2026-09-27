import React, { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";

const FINISHED = new Set(["succeeded", "failed", "canceled"]);
const AMOUNTS = [10, 25, 50, 100];

function groupSources(sources) {
  const groups = new Map();
  for (const source of sources) {
    const key = source.group || "Other";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(source);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

// Find new recipes on sites the owner chose. Sources start switched off, and
// each run imports at most a set number of recipes.
export default function DiscoverPage({ canImport, onNotice, onError }) {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState(25);
  const [runId, setRunId] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [newSource, setNewSource] = useState("");
  const [openGroups, setOpenGroups] = useState(() => new Set());

  const discover = useQuery({ queryKey: ["discover"], queryFn: () => api("/discover") });
  const data = discover.data;
  const sources = data?.sources || [];
  const groups = useMemo(() => groupSources(sources), [sources]);

  const run = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api(`/runs/${runId}`),
    enabled: Boolean(runId),
    refetchInterval: (query) => (FINISHED.has(query.state.data?.status) ? false : 2000),
  });
  const running = (Boolean(runId) && !FINISHED.has(run.data?.status)) || Boolean(data?.running);

  useEffect(() => {
    if (!runId || !FINISHED.has(run.data?.status)) return;
    const preview = run.data.options?.dry_run !== false;
    setRunId("");
    queryClient.invalidateQueries({ queryKey: ["discover"] });
    if (run.data.status === "succeeded") {
      onNotice?.(preview ? "Preview finished. Nothing was imported yet." : "Import finished.", { tone: preview ? "info" : "success" });
      if (!preview) queryClient.invalidateQueries({ queryKey: ["library"] });
    } else {
      onNotice?.("The run didn't finish. Open Tasks to see what happened.", { tone: "warning" });
    }
  }, [runId, run.data?.status]);

  const start = useMutation({
    mutationFn: ({ live }) =>
      api("/runs", {
        method: "POST",
        body: { task_id: "recipe-dredger", options: { dry_run: !live, max_total: amount }, confirmed: live },
      }),
    onSuccess: (newRun) => {
      setConfirmOpen(false);
      setRunId(newRun.run_id);
    },
    onError: (exc) => onError?.(exc),
  });

  const toggle = useMutation({
    mutationFn: ({ ids, enabled }) => api("/discover/sources/enabled", { method: "POST", body: { ids, enabled } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discover"] }),
    onError: (exc) => onError?.(exc),
  });

  const add = useMutation({
    mutationFn: (url) => api("/settings/dredger-sites", { method: "POST", body: { url }, timeout: 45000 }),
    onSuccess: () => {
      setNewSource("");
      onNotice?.("Source added and switched on.");
      queryClient.invalidateQueries({ queryKey: ["discover"] });
    },
    onError: (exc) => onError?.(exc),
  });

  const remove = useMutation({
    mutationFn: (id) => api(`/settings/dredger-sites/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discover"] }),
    onError: (exc) => onError?.(exc),
  });

  const check = useMutation({
    mutationFn: (ids) => api("/settings/dredger-sites/validate", { method: "POST", body: { site_ids: ids }, timeout: 120000 }),
    onError: (exc) => onError?.(exc),
  });
  const unreachable = (check.data?.results || []).filter((result) => !result.reachable);

  const enabledCount = data?.enabled_count || 0;
  const lastRun = data?.last_run;

  return (
    <section className="discover">
      <header className="organize-head">
        <h2>Discover</h2>
        <p className="muted">
          Find new recipes on sites you choose. CookDex imports only pages that are real recipes, and it waits between
          requests so sites aren't overloaded.
        </p>
      </header>

      <section className="discover-run" aria-labelledby="discover-run-title">
        <div className="discover-run-copy">
          <h3 id="discover-run-title">
            {enabledCount ? `${enabledCount} source${enabledCount === 1 ? "" : "s"} switched on` : "No sources switched on yet"}
          </h3>
          <p className="muted">
            {data?.imported_total ? `${data.imported_total} recipes imported from them so far. ` : ""}
            {enabledCount ? "Preview first to see what a run would bring in." : "Switch on a few sources below to start."}
          </p>
        </div>
        <div className="discover-run-controls">
          <label htmlFor="discover-amount" className="muted tiny">At most</label>
          <select id="discover-amount" value={amount} onChange={(e) => setAmount(Number(e.target.value))}>
            {AMOUNTS.map((n) => <option key={n} value={n}>{n} new recipes</option>)}
          </select>
          <button type="button" className="ghost" disabled={!enabledCount || running} onClick={() => start.mutate({ live: false })}>
            Preview
          </button>
          <button type="button" className="primary" disabled={!enabledCount || running || !canImport} onClick={() => setConfirmOpen(true)}>
            Import now
          </button>
        </div>
        {running ? (
          <p className="library-banner" role="status">
            <Icon name="loader" className="spin" /> Visiting sources and checking pages. This can take a few minutes.
          </p>
        ) : null}
        {!canImport && enabledCount ? (
          <p className="muted tiny">An owner has to approve imports. You can still preview.</p>
        ) : null}
      </section>

      {lastRun ? (
        <section className="library-section" aria-labelledby="discover-last-title">
          <div className="library-section-head">
            <h3 id="discover-last-title">
              {lastRun.preview ? "Last preview" : "Last import"}
              {lastRun.finished_at ? <span className="muted tiny"> · {formatDistanceToNow(new Date(lastRun.finished_at), { addSuffix: true })}</span> : null}
            </h3>
          </div>
          {lastRun.status !== "succeeded" ? (
            <p className="muted">It didn't finish. Open Tasks to see what happened.</p>
          ) : lastRun.count === 0 ? (
            <p className="muted">No new recipes {lastRun.preview ? "would be" : "were"} imported. Every page found was already known or wasn't a recipe.</p>
          ) : (
            <>
              <p>
                {lastRun.preview
                  ? `Found ${lastRun.count} recipe${lastRun.count === 1 ? "" : "s"} to import.`
                  : `Imported ${lastRun.count} recipe${lastRun.count === 1 ? "" : "s"}. They're in your Library.`}
              </p>
              <ul className="discover-found">
                {lastRun.items.map((item) => (
                  <li key={item.url}>
                    <a href={item.url} target="_blank" rel="noreferrer">{item.url.replace(/^https?:\/\/(www\.)?/, "")}</a>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      ) : null}

      <section className="library-section" aria-labelledby="discover-sources-title">
        <div className="library-section-head">
          <h3 id="discover-sources-title">Sources</h3>
          <span className="muted tiny">{data ? `${data.total} suggested and added` : ""}</span>
        </div>

        <form
          className="discover-add"
          onSubmit={(e) => {
            e.preventDefault();
            if (newSource.trim()) add.mutate(newSource.trim());
          }}
        >
          <input
            type="url"
            id="discover-new-source"
            aria-label="Add a recipe site"
            placeholder="https://your-favorite-recipe-site.com"
            value={newSource}
            onChange={(e) => setNewSource(e.target.value)}
          />
          <button type="submit" className="ghost" disabled={add.isPending || !newSource.trim()}>
            {add.isPending ? "Checking the site…" : "Add source"}
          </button>
        </form>

        {enabledCount ? (
          <div className="discover-check">
            <button
              type="button"
              className="ghost small"
              disabled={check.isPending}
              onClick={() => check.mutate(sources.filter((source) => source.enabled).map((source) => source.id))}
            >
              {check.isPending ? "Checking…" : "Check sources that are on"}
            </button>
            {check.isSuccess ? (
              unreachable.length ? (
                <span className="discover-check-result">
                  <Icon name="alertTriangle" /> {unreachable.length} can't be reached right now.
                  <button
                    type="button"
                    className="link-inline"
                    onClick={() => {
                      toggle.mutate({ ids: unreachable.map((result) => result.id), enabled: false });
                      check.reset();
                    }}
                  >
                    Switch them off
                  </button>
                </span>
              ) : (
                <span className="discover-check-result ok"><Icon name="check-circle" /> All reachable.</span>
              )
            ) : null}
          </div>
        ) : null}

        {discover.isLoading ? <p className="muted">Loading sources…</p> : null}
        <div className="discover-groups">
          {groups.map(([group, members]) => {
            const on = members.filter((s) => s.enabled).length;
            const open = openGroups.has(group) || on > 0;
            return (
              <section key={group} className="discover-group">
                <header>
                  <button
                    type="button"
                    className="discover-group-toggle"
                    aria-expanded={open}
                    onClick={() =>
                      setOpenGroups((prev) => {
                        const next = new Set(prev);
                        if (next.has(group)) next.delete(group);
                        else next.add(group);
                        return next;
                      })
                    }
                  >
                    <Icon name="chevron" /> <strong>{group}</strong>
                    <span className="muted tiny">{on} of {members.length} on</span>
                  </button>
                  <button
                    type="button"
                    className="ghost small"
                    onClick={() => toggle.mutate({ ids: members.map((s) => s.id), enabled: on !== members.length })}
                  >
                    {on === members.length ? "Switch all off" : "Switch all on"}
                  </button>
                </header>
                {open ? (
                  <ul className="discover-sources">
                    {members.map((source) => (
                      <li key={source.id}>
                        <label className="switch">
                          <input
                            type="checkbox"
                            checked={source.enabled}
                            onChange={() => toggle.mutate({ ids: [source.id], enabled: !source.enabled })}
                          />
                          <span>{source.label}</span>
                        </label>
                        <span className="muted tiny">
                          {source.imported ? `${source.imported} imported` : "Nothing imported yet"}
                          {source.last_imported_at ? ` · last ${formatDistanceToNow(new Date(source.last_imported_at), { addSuffix: true })}` : ""}
                        </span>
                        <button type="button" className="ghost small" aria-label={`Remove ${source.label}`} onClick={() => remove.mutate(source.id)}>
                          <Icon name="x" />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
            );
          })}
        </div>
      </section>

      <Dialog.Root open={confirmOpen} onOpenChange={setConfirmOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="sheet-overlay" />
          <Dialog.Content className="review-sheet review-sheet-small" aria-describedby="discover-confirm-desc">
            <header className="review-sheet-head">
              <div>
                <Dialog.Title className="review-sheet-title">Import up to {amount} new recipes?</Dialog.Title>
                <Dialog.Description id="discover-confirm-desc" className="muted">
                  From {enabledCount} source{enabledCount === 1 ? "" : "s"}. Only pages that are real recipes are imported, and
                  recipes you already have are skipped. You can review and clean them up from the Library afterwards.
                </Dialog.Description>
              </div>
            </header>
            <footer className="review-sheet-foot">
              <Dialog.Close className="ghost">Cancel</Dialog.Close>
              <button type="button" className="primary" disabled={start.isPending} onClick={() => start.mutate({ live: true })}>
                {start.isPending ? "Starting…" : "Import"}
              </button>
            </footer>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
