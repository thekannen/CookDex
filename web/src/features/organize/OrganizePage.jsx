import React, { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { useProvider } from "../provider/useProvider";
import CookbooksPanel from "./CookbooksPanel";
import ImportExport from "./ImportExport";
import IngredientsPanel from "./IngredientsPanel";
import LabelsPanel from "./LabelsPanel";
import StarterPacks, { SPARSE_BELOW } from "./StarterPacks";
import { describeChange, groupChanges, stagedSummary } from "./model.mjs";

const FINISHED = new Set(["succeeded", "failed", "canceled"]);

function useOrganizers(kind) {
  return useQuery({
    queryKey: ["organize", kind],
    queryFn: () => api(`/organize/${kind}`, { timeout: 60000 }),
    enabled: Boolean(kind),
    staleTime: 30000,
  });
}

// Tags, categories, tools, cookbooks, labels, foods and units, edited in Mealie itself. Changes are staged
// here and applied together as one run, with a backup first.
export default function OrganizePage({ canApply, onNotice, onError }) {
  const queryClient = useQueryClient();
  const provider = useProvider();
  const KINDS = provider.term_kinds.map((id) => ({
    id,
    label: provider.vocabulary.terms?.[id] || id,
    singular: provider.vocabulary.term_singular?.[id] || id,
  }));
  const collectionsLabel = provider.vocabulary.collections || "Cookbooks";
  if (provider.has("rule_collections")) {
    KINDS.push({ id: "cookbooks", label: collectionsLabel, singular: collectionsLabel.toLowerCase().replace(/s$/, "") });
  }
  if (provider.has("labels")) {
    KINDS.push({ id: "labels", label: "Labels", singular: "label" });
  }
  if (provider.has("foods")) KINDS.push({ id: "foods", label: "Foods", singular: "food" });
  if (provider.has("units")) KINDS.push({ id: "units", label: "Units", singular: "unit" });
  const [kind, setKind] = useState(provider.term_kinds[0] || "tags");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [staged, setStaged] = useState({}); // item id -> change
  const [reviewOpen, setReviewOpen] = useState(false);
  const [applyRunId, setApplyRunId] = useState("");

  const isCookbooks = kind === "cookbooks";
  const isLabels = kind === "labels";
  const isIngredients = kind === "foods" || kind === "units";
  const isPanel = isCookbooks || isLabels || isIngredients;
  const list = useOrganizers(isPanel ? null : kind);
  const items = list.data?.items || [];
  const byId = useMemo(() => new Map(items.map((item) => [item.id, item])), [items]);
  const changes = Object.values(staged);

  const applyRun = useQuery({
    queryKey: ["run", applyRunId],
    queryFn: () => api(`/runs/${applyRunId}`),
    enabled: Boolean(applyRunId),
    refetchInterval: (query) => (FINISHED.has(query.state.data?.status) ? false : 1200),
  });
  const applying = Boolean(applyRunId) && !FINISHED.has(applyRun.data?.status);

  useEffect(() => {
    if (!applyRunId || !FINISHED.has(applyRun.data?.status)) return;
    const runId = applyRunId;
    setApplyRunId("");
    api(`/runs/${runId}/result`)
      .then((result) => {
        const items = (result?.results || []).filter((e) => e.kind === "taxonomy_change").flatMap((e) => e.items);
        const applied = items.filter((i) => i.status === "applied").length;
        const skipped = items.filter((i) => i.status !== "applied");
        if (skipped.length) {
          onNotice?.(
            `Applied ${applied} of ${items.length} changes. ${skipped.length} skipped: ${skipped[0].error || "see Tasks for details"}`,
            { tone: "warning" }
          );
        } else {
          onNotice?.(`Applied ${applied} change${applied === 1 ? "" : "s"} to Mealie.`);
        }
      })
      .catch(() => onNotice?.("Changes finished. Open Tasks to see the details.", { tone: "info" }));
    setStaged({});
    queryClient.invalidateQueries({ queryKey: ["organize"] });
    queryClient.invalidateQueries({ queryKey: ["library"] });
  }, [applyRunId, applyRun.data?.status]);

  const apply = useMutation({
    mutationFn: () =>
      api("/runs", {
        method: "POST",
        body: {
          task_id: "organize-apply",
          options: { dry_run: false, backup_first: true, plan: { organize: { changes } } },
          confirmed: true,
        },
      }),
    onSuccess: (run) => {
      setReviewOpen(false);
      setApplyRunId(run.run_id);
    },
    onError: (exc) => onError?.(exc),
  });

  function stage(change) {
    setStaged((prev) => ({ ...prev, [change.id]: change }));
  }
  function unstage(id) {
    setStaged((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }

  const visible = items.filter((item) => {
    if (search && !item.name.toLowerCase().includes(search.trim().toLowerCase())) return false;
    if (filter === "suggested") return Boolean(item.merge_into);
    if (filter === "unused") return item.count === 0;
    return true;
  });
  // Items that are going away can't be a merge target.
  const targets = items.filter((item) => !["merge", "delete"].includes(staged[item.id]?.op));
  const kindMeta = KINDS.find((k) => k.id === kind) || { id: kind, label: kind, singular: kind };
  const created = changes.filter((c) => c.kind === kind && c.op === "create");
  const sparse = Boolean(list.data) && list.data.total < SPARSE_BELOW;
  const starterPacks = (prominent) => (
    <StarterPacks
      kind={kind}
      noun={{ singular: kindMeta.singular, plural: kindMeta.label.toLowerCase() }}
      existingNames={items.map((item) => item.name)}
      staged={staged}
      onStage={stage}
      prominent={prominent}
    />
  );

  function stageAllSuggestions() {
    for (const item of items) {
      if (item.merge_into && !staged[item.id]) {
        stage({ op: "merge", kind, id: item.id, name: item.name, target_id: item.merge_into.id, target_name: item.merge_into.name });
      }
    }
  }
  function stageAllUnused() {
    for (const item of items) {
      if (item.count === 0 && !staged[item.id]) stage({ op: "delete", kind, id: item.id, name: item.name });
    }
  }

  return (
    <section className="organize">
      <header className="organize-head page-head-split">
        <div>
          <h2>Organize</h2>
          <p className="muted">
            {KINDS.map((k) => k.label.toLowerCase()).join(", ").replace(/^./, (c) => c.toUpperCase())} in {provider.vocabulary.backend}. Changes are staged until you apply them.
          </p>
        </div>
        <div className="organize-head-actions">
          <ImportExport backend={provider.vocabulary.backend} onStage={stage} onNotice={onNotice} onError={onError} />
        </div>
      </header>

      <div className="segmented" role="tablist" aria-label="What to organize">
        {KINDS.map((option) => (
          <button
            key={option.id}
            type="button"
            role="tab"
            aria-selected={kind === option.id}
            className={kind === option.id ? "active" : ""}
            onClick={(e) => {
              setKind(option.id);
              setFilter("all");
              e.currentTarget.scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: "smooth" });
            }}
          >
            {option.label}
            {kind === option.id && !isPanel && list.data ? <span className="segmented-count">{list.data.total}</span> : null}
          </button>
        ))}
      </div>

      {isCookbooks ? (
        <CookbooksPanel label={collectionsLabel} staged={staged} onStage={stage} onUnstage={unstage} />
      ) : isLabels ? (
        <LabelsPanel staged={staged} onStage={stage} onUnstage={unstage} />
      ) : isIngredients ? (
        <IngredientsPanel key={kind} kind={kind} withLabels={kind === "foods" && provider.has("labels")} staged={staged} onStage={stage} onUnstage={unstage} />
      ) : (
        <>
      {sparse ? starterPacks(true) : null}
      <div className="organize-toolbar">
        <input
          type="search"
          id="organize-search"
          aria-label={`Search ${kindMeta.label.toLowerCase()}`}
          placeholder={`Search ${kindMeta.label.toLowerCase()}`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="chip-row" role="group" aria-label="Show">
          {[
            { id: "all", label: "All" },
            { id: "suggested", label: `Suggested merges${list.data ? ` (${list.data.suggested_merges})` : ""}` },
            { id: "unused", label: `Unused${list.data ? ` (${list.data.unused})` : ""}` },
          ].map((option) => (
            <button
              key={option.id}
              type="button"
              className={`chip-btn${filter === option.id ? " active" : ""}`}
              aria-pressed={filter === option.id}
              onClick={() => setFilter(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>
        {filter === "suggested" && list.data?.suggested_merges ? (
          <button type="button" className="ghost small" onClick={stageAllSuggestions}>Merge all suggested</button>
        ) : null}
        {filter === "unused" && list.data?.unused ? (
          <button type="button" className="ghost small" onClick={stageAllUnused}>Delete all unused</button>
        ) : null}
        {list.data && !sparse ? starterPacks(false) : null}
      </div>

      {list.isLoading ? (
        <p className="muted">Loading {kindMeta.label.toLowerCase()} from Mealie…</p>
      ) : list.isError ? (
        <p className="welcome-message error" role="alert"><Icon name="x-circle" /> {String(list.error?.message || list.error)}</p>
      ) : visible.length === 0 && created.length === 0 ? (
        <p className="muted">{filter === "all" ? `No ${kindMeta.label.toLowerCase()} match.` : "Nothing here right now."}</p>
      ) : (
        <div className="organize-table" role="table" aria-label={kindMeta.label}>
          <div className="organize-row organize-row-head" role="row">
            <span role="columnheader">Name</span>
            <span role="columnheader" className="num">Recipes</span>
            <span role="columnheader">Suggestion</span>
            <span role="columnheader" className="sr-only">Actions</span>
          </div>
          {created.map((change) => (
            <div key={change.id} className="organize-row is-staged" role="row">
              <span role="cell" className="organize-name">
                <strong>{change.to.name}</strong> <span className="staged-note">New</span>
              </span>
              <span role="cell" className="num">0</span>
              <span role="cell" />
              <span role="cell" className="organize-actions">
                <button type="button" className="ghost small" onClick={() => unstage(change.id)}>Undo</button>
              </span>
            </div>
          ))}
          {visible.map((item) => (
            <OrganizeRow
              key={item.id}
              item={item}
              kind={kind}
              change={staged[item.id]}
              targets={targets.filter((t) => t.id !== item.id)}
              onStage={stage}
              onUnstage={() => unstage(item.id)}
            />
          ))}
        </div>
      )}
        </>
      )}

      {changes.length > 0 || applying ? (
        <div className="organize-tray" role="region" aria-label="Staged changes">
          <span>
            {applying ? (
              <><Icon name="loader" className="spin" /> Applying changes to Mealie…</>
            ) : (
              stagedSummary(changes)
            )}
          </span>
          {!applying ? (
            <span className="organize-tray-actions">
              <button type="button" className="ghost" onClick={() => setStaged({})}>Discard</button>
              <button type="button" className="primary" onClick={() => setReviewOpen(true)}>Review and apply</button>
            </span>
          ) : null}
        </div>
      ) : null}

      <Dialog.Root open={reviewOpen} onOpenChange={setReviewOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="sheet-overlay" />
          <Dialog.Content className="review-sheet" aria-describedby="organize-review-desc">
            <header className="review-sheet-head">
              <div>
                <Dialog.Title className="review-sheet-title">Apply {changes.length} change{changes.length === 1 ? "" : "s"} to Mealie?</Dialog.Title>
                <Dialog.Description id="organize-review-desc" className="muted">
                  {changes.some((c) => c.op === "merge" && ["tags", "categories", "tools"].includes(c.kind)) ? "Merges move recipes to the kept name and update cookbook filters. " : ""}
                  {changes.some((c) => c.op === "merge" && (c.kind === "foods" || c.kind === "units")) ? "Food and unit merges repoint every ingredient and keep the old name as an alias. " : ""}
                  {changes.some((c) => c.op === "merge" && c.kind === "labels") ? "Label merges move foods to the kept label. " : ""}
                  A {provider.vocabulary.backend} backup is made first.
                </Dialog.Description>
              </div>
              <Dialog.Close className="ghost small" aria-label="Close"><Icon name="x" /></Dialog.Close>
            </header>
            <div className="review-sheet-body">
              {groupChanges(changes).map(([title, group]) => (
                <section key={title} className="review-group">
                  <h4>{title} <span className="review-count">{group.length}</span></h4>
                  <ul className="review-list">
                    {group.map((change) => (
                      <li key={change.id} className="review-row">
                        <Icon name={change.op === "delete" ? "trash" : change.op === "merge" ? "layers" : change.op === "create" ? "plus" : "pencil"} />
                        <span className="review-row-main">
                          <strong>{describeChange(change)}</strong>
                          {change.op !== "rename" && byId.get(change.id)?.count ? (
                            <span className="muted tiny">
                              {change.op === "merge"
                                ? `${byId.get(change.id).count} recipes move to "${change.target_name}"`
                                : `Removed from ${byId.get(change.id).count} recipes`}
                            </span>
                          ) : null}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
            <footer className="review-sheet-foot">
              <span className="muted tiny">
                {canApply ? "Nothing changes until you apply." : "An owner has to approve changes to Mealie's organizers."}
              </span>
              <button type="button" className="primary" disabled={!canApply || apply.isPending} onClick={() => apply.mutate()}>
                {apply.isPending ? "Starting…" : `Apply ${changes.length} change${changes.length === 1 ? "" : "s"}`}
              </button>
            </footer>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}

function OrganizeRow({ item, kind, change, targets, onStage, onUnstage }) {
  const [mode, setMode] = useState(""); // "", "rename", "merge"
  const [draft, setDraft] = useState(item.name);
  const [target, setTarget] = useState(item.merge_into?.id || "");

  if (change) {
    return (
      <div className={`organize-row is-staged staged-${change.op}`} role="row">
        <span role="cell" className="organize-name">
          <span className="old">{item.name}</span>
          <span className="staged-note">{describeChange(change, { short: true })}</span>
        </span>
        <span role="cell" className="num">{item.count}</span>
        <span role="cell" />
        <span role="cell" className="organize-actions">
          <button type="button" className="ghost small" onClick={onUnstage}>Undo</button>
        </span>
      </div>
    );
  }

  return (
    <div className="organize-row" role="row">
      <span role="cell" className="organize-name">
        {mode === "rename" ? (
          <form
            className="inline-edit"
            onSubmit={(e) => {
              e.preventDefault();
              const to = draft.trim();
              if (to && to !== item.name) onStage({ op: "rename", kind, id: item.id, name: item.name, to });
              setMode("");
            }}
          >
            <input
              aria-label={`New name for ${item.name}`}
              value={draft}
              autoFocus
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Escape") setMode(""); }}
            />
            <button type="submit" className="primary small">Stage</button>
            <button type="button" className="ghost small" onClick={() => setMode("")}>Cancel</button>
          </form>
        ) : mode === "merge" ? (
          <form
            className="inline-edit"
            onSubmit={(e) => {
              e.preventDefault();
              const chosen = targets.find((t) => t.id === target);
              if (chosen) onStage({ op: "merge", kind, id: item.id, name: item.name, target_id: chosen.id, target_name: chosen.name });
              setMode("");
            }}
          >
            <span className="muted tiny">Merge “{item.name}” into</span>
            <select aria-label={`Merge ${item.name} into`} value={target} onChange={(e) => setTarget(e.target.value)} autoFocus>
              <option value="">Choose…</option>
              {targets.map((t) => (
                <option key={t.id} value={t.id}>{t.name} ({t.count})</option>
              ))}
            </select>
            <button type="submit" className="primary small" disabled={!target}>Stage</button>
            <button type="button" className="ghost small" onClick={() => setMode("")}>Cancel</button>
          </form>
        ) : (
          <strong>{item.name}</strong>
        )}
      </span>
      <span role="cell" className={`num${item.count === 0 ? " muted" : ""}`}>{item.count}</span>
      <span role="cell" className="organize-suggestion">
        {item.merge_into ? (
          <>
            <span>Looks like “{item.merge_into.name}”</span>
            <button
              type="button"
              className="ghost small"
              onClick={() => onStage({ op: "merge", kind, id: item.id, name: item.name, target_id: item.merge_into.id, target_name: item.merge_into.name })}
            >
              Merge
            </button>
          </>
        ) : item.count === 0 ? (
          <span className="muted">Not used by any recipe</span>
        ) : null}
      </span>
      <span role="cell" className="organize-actions">
        {mode ? null : (
          <>
            <button type="button" className="ghost small" onClick={() => { setDraft(item.name); setMode("rename"); }}>Rename</button>
            <button type="button" className="ghost small" onClick={() => setMode("merge")}>Merge…</button>
            <button
              type="button"
              className="ghost small danger-text"
              onClick={() => onStage({ op: "delete", kind, id: item.id, name: item.name })}
              title={item.count ? `Removes it from ${item.count} recipes` : undefined}
            >
              Delete
            </button>
          </>
        )}
      </span>
    </div>
  );
}
