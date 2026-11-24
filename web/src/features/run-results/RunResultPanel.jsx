import React, { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import SelectAllToggle from "../../components/SelectAllToggle";
import { api } from "../../utils.jsx";
import {
  DELETE_GROUP_COPY,
  applyLabel,
  applyOptions,
  buildPlan,
  collectItems,
  defaultSelection,
  describeCategorize,
  describeResult,
  sortCategorize,
  hasItems,
  planSize,
  reviewTarget,
  runWasPreview,
  scopeToTask,
} from "./model.mjs";

const FINISHED = new Set(["succeeded", "failed", "canceled"]);

export function useRunResult(run) {
  const finished = FINISHED.has(run?.status);
  return useQuery({
    queryKey: ["run-result", run?.run_id, run?.status],
    queryFn: () => api(`/runs/${run.run_id}/result`),
    enabled: Boolean(run?.run_id) && finished,
    staleTime: Infinity,
  });
}

// Summary sentence for a finished run, plus the review sheet when the run
// recorded individual changes. Renders nothing for runs without items.
export default function RunResultPanel({ run, taskTitle, canApply, onApplied, onError }) {
  const { data } = useRunResult(run);
  const collected = useMemo(() => collectItems(data?.results), [data]);
  const [open, setOpen] = useState(false);

  if (!run || !data || !hasItems(collected)) return null;

  const preview = runWasPreview(run);
  const target = reviewTarget(run);
  const reviewable = preview && run.status === "succeeded" && Boolean(target);
  const title = typeof taskTitle === "function" ? taskTitle(target?.task_id || run.task_id) : taskTitle;
  const shown = reviewable ? scopeToTask(collected, target.task_id) : collected;

  return (
    <div className={`run-result ${preview ? "is-preview" : "is-applied"}`}>
      <p className="run-result-sentence">{describeResult(collected, { preview })}</p>
      <button type="button" className={reviewable ? "primary small" : "ghost small"} onClick={() => setOpen(true)}>
        <Icon name={reviewable ? "check-circle" : "list"} />
        {reviewable ? "Review changes" : "See each change"}
      </button>
      <ReviewSheet
        key={run.run_id}
        open={open}
        onOpenChange={setOpen}
        run={run}
        taskTitle={title}
        collected={shown}
        reviewable={reviewable}
        canApply={canApply}
        onApplied={onApplied}
        onError={onError}
      />
    </div>
  );
}

export function ReviewSheet({ open, onOpenChange, run, taskTitle, collected, reviewable, canApply, onApplied, onError }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState(() => defaultSelection(collected));
  const [editedNames, setEditedNames] = useState({});
  const [backupFirst, setBackupFirst] = useState(true);
  const plan = useMemo(
    () => buildPlan(collected, selected, editedNames, { runId: run?.run_id }),
    [collected, selected, editedNames, run?.run_id],
  );
  const { deletes, renames, categorize } = planSize(plan);
  const nothingSelected = deletes + renames + categorize === 0;
  const target = reviewTarget(run) || { task_id: run?.task_id, options: run?.options };
  const categorizeItems = useMemo(
    () => (reviewable ? collected.categorize || [] : sortCategorize(collected.categorize || [])),
    [collected, reviewable],
  );
  const onlyCategorize =
    categorizeItems.length > 0 &&
    collected.renames.length === 0 &&
    Object.values(collected.deleteGroups).every((items) => items.length === 0);
  // "Both" previews ran rules too; applying a review writes only the AI's reviewed changes.
  const rulesLeftOut = onlyCategorize && (target.options?.method || "both") === "both";

  const apply = useMutation({
    mutationFn: () =>
      api("/runs", {
        method: "POST",
        body: {
          task_id: target.task_id,
          options: applyOptions(target.options, plan, { backupFirst, taskId: target.task_id }),
          confirmed: true,
        },
      }),
    onSuccess: (newRun) => {
      queryClient.invalidateQueries({ queryKey: ["run-result"] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      onOpenChange(false);
      onApplied?.(newRun);
    },
    onError: (exc) => onError?.(exc),
  });

  // "Leave as is": remembered by CookDex, so cleanups and the Library leave
  // the recipe alone until it changes in Mealie.
  const [left, setLeft] = useState(() => new Set());
  const leave = useMutation({
    mutationFn: (items) =>
      api("/library/kept", {
        method: "POST",
        body: { items: items.map(({ slug, name, kind, updated_at }) => ({ slug, name, kind, updated_at: updated_at || "" })) },
      }),
    onSuccess: (_, items) => {
      const slugs = new Set(items.map((item) => item.slug));
      setLeft((prev) => new Set([...prev, ...slugs]));
      setSelected((prev) => new Set([...prev].filter((key) => !slugs.has(key.slice(key.indexOf(":") + 1)))));
      queryClient.invalidateQueries({ queryKey: ["library"] });
    },
    onError: (exc) => onError?.(exc),
  });
  const leaveRename = (item) => ({ slug: item.slug, name: item.old_name, kind: item.conflict ? "name_clash" : "rename", updated_at: item.updated_at });
  const leaveDelete = (group) => (item) => ({ slug: item.slug, name: item.name || item.slug, kind: group, updated_at: item.updated_at });

  function toggle(key) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const plannedCategorize = categorizeItems.filter((item) => item.status === "planned");
  const deleteGroups = Object.entries(collected.deleteGroups)
    .map(([group, items]) => [group, items.filter((item) => !left.has(item.slug))])
    .filter(([, items]) => items.length > 0);
  const shownRenames = collected.renames.filter((item) => !left.has(item.slug));
  // Duplicates aren't offered: keeping both copies is just leaving them unticked.
  const canLeave = (group) => reviewable && group !== "duplicate";
  // What each list's Select all ticks: planned items, minus renames of recipes
  // removed in this batch (those checkboxes are disabled).
  const deleteKeys = (items) => items.filter((item) => item.status === "planned").map((item) => `delete:${item.slug}`);
  const renameKeys = shownRenames
    .filter((item) => item.status === "planned" && !selected.has(`delete:${item.slug}`))
    .map((item) => `rename:${item.slug}`);
  const categorizeKeys = plannedCategorize.map((item) => `categorize:${item.slug}`);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="review-sheet" aria-describedby="review-sheet-desc">
          <header className="review-sheet-head">
            <div>
              <Dialog.Title className="review-sheet-title">
                {reviewable ? `Review ${taskTitle}` : `${taskTitle}: what changed`}
              </Dialog.Title>
              <Dialog.Description id="review-sheet-desc" className="muted">
                {reviewable
                  ? onlyCategorize
                    ? "Untick any recipe you don't want changed. Applying uses these suggestions, so the AI isn't asked again."
                    : "Untick anything you want to keep. You can edit a new name before applying."
                  : describeResult(collected, { preview: run.options?.dry_run !== false })}
              </Dialog.Description>
            </div>
            <Dialog.Close className="ghost small" aria-label="Close">
              <Icon name="x" />
            </Dialog.Close>
          </header>

          <div className="review-sheet-body">
            {deleteGroups.map(([group, items]) => (
              <section key={group} className="review-group">
                <h4>
                  {DELETE_GROUP_COPY[group].title} <span className="review-count">{items.length}</span>
                  {reviewable ? (
                    <SelectAllToggle
                      keys={deleteKeys(items)}
                      selected={selected}
                      onChange={setSelected}
                      label={DELETE_GROUP_COPY[group].title}
                    />
                  ) : null}
                  {canLeave(group) && items.length > 1 ? (
                    <LeaveAllButton count={items.length} disabled={leave.isPending} onClick={() => leave.mutate(items.map(leaveDelete(group)))} />
                  ) : null}
                </h4>
                {reviewable ? <p className="muted tiny">{DELETE_GROUP_COPY[group].hint}</p> : null}
                <ul className="review-list">
                  {items.map((item) => {
                    const key = `delete:${item.slug}`;
                    return (
                      <li key={key} className={`review-row${reviewable && !selected.has(key) ? " is-kept" : ""}`}>
                        {reviewable ? (
                          <input
                            type="checkbox"
                            id={`review-${key}`}
                            checked={selected.has(key)}
                            onChange={() => toggle(key)}
                          />
                        ) : (
                          <StatusChip status={item.status} />
                        )}
                        <label htmlFor={`review-${key}`} className="review-row-main">
                          <strong>{item.name || item.slug}</strong>
                          <span className="muted tiny">
                            {group === "duplicate" && item.keep_name
                              ? item.keep_new_name
                                ? `Keeps the more complete copy, "${item.keep_name}", renamed "${item.keep_new_name}"`
                                : `Keeps the more complete copy, "${item.keep_name}"`
                              : item.reason}
                            {item.error ? ` · ${item.error}` : ""}
                          </span>
                        </label>
                        {canLeave(group) ? (
                          <LeaveButton name={item.name || item.slug} disabled={leave.isPending} onClick={() => leave.mutate([leaveDelete(group)(item)])} />
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}

            {shownRenames.length > 0 && (
              <section className="review-group">
                <h4>
                  Names to clean up <span className="review-count">{shownRenames.length}</span>
                  {reviewable ? (
                    <SelectAllToggle keys={renameKeys} selected={selected} onChange={setSelected} label="Names to clean up" />
                  ) : null}
                  {reviewable && shownRenames.length > 1 ? (
                    <LeaveAllButton count={shownRenames.length} disabled={leave.isPending} onClick={() => leave.mutate(shownRenames.map(leaveRename))} />
                  ) : null}
                </h4>
                <ul className="review-list">
                  {shownRenames.map((item) => {
                    const key = `rename:${item.slug}`;
                    const removed = reviewable && selected.has(`delete:${item.slug}`);
                    const active = selected.has(key) && !removed;
                    return (
                      <li key={key} className={`review-row rename${reviewable && !active ? " is-kept" : ""}`}>
                        {reviewable ? (
                          <input
                            type="checkbox"
                            aria-label={`Rename ${item.old_name}`}
                            checked={active}
                            disabled={removed}
                            title={removed ? "This recipe is removed in this batch." : undefined}
                            onChange={() => toggle(key)}
                          />
                        ) : (
                          <StatusChip status={item.status} />
                        )}
                        <span className="rename-old" title={item.old_name}>{item.old_name}</span>
                        <span className="rename-arrow" aria-hidden="true">→</span>
                        {reviewable ? (
                          <input
                            type="text"
                            className="rename-new"
                            id={`rename-${item.slug}`}
                            aria-label={`New name for ${item.old_name}`}
                            value={removed ? "Removed in this batch" : editedNames[item.slug] ?? item.new_name}
                            disabled={!active}
                            onChange={(e) => setEditedNames((prev) => ({ ...prev, [item.slug]: e.target.value }))}
                          />
                        ) : (
                          <strong className="rename-new-text">{item.new_name}</strong>
                        )}
                        {item.conflict ? (
                          <span className="rename-conflict muted tiny">
                            {item.conflict === "existing"
                              ? `Another recipe is already called “${item.conflict_with}”. It may be a duplicate; edit the name or leave it unticked.`
                              : "Another rename in this list gets the same name. Edit one of them before ticking."}
                          </span>
                        ) : null}
                        {!reviewable && !item.conflict && item.error ? (
                          <span className="rename-conflict muted tiny">{item.error}</span>
                        ) : null}
                        {reviewable ? (
                          <LeaveButton name={item.old_name} disabled={leave.isPending} onClick={() => leave.mutate([leaveRename(item)])} />
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            {categorizeItems.length > 0 && (
              <section className="review-group">
                <h4>
                  {reviewable ? "Recipes to tag or categorize" : "Recipes"}{" "}
                  <span className="review-count">{categorizeItems.length}</span>
                  {reviewable ? (
                    <SelectAllToggle keys={categorizeKeys} selected={selected} onChange={setSelected} label="Recipes to tag or categorize" />
                  ) : null}
                </h4>
                <ul className="review-list">
                  {categorizeItems.map((item) => {
                    const key = `categorize:${item.slug}`;
                    const detail = describeCategorize(item);
                    return (
                      <li key={key} className={`review-row${reviewable && !selected.has(key) ? " is-kept" : ""}`}>
                        {reviewable ? (
                          <input
                            type="checkbox"
                            id={`review-${key}`}
                            checked={selected.has(key)}
                            disabled={item.status !== "planned"}
                            onChange={() => toggle(key)}
                          />
                        ) : (
                          <StatusChip status={item.status} skippedLabel="Skipped" />
                        )}
                        <label htmlFor={`review-${key}`} className="review-row-main">
                          <strong>{item.name || item.slug}</strong>
                          <span className="muted tiny">
                            {detail}
                            {item.error ? `${detail ? " · " : ""}${item.error}` : ""}
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}
          </div>

          <footer className="review-sheet-foot">
            {reviewable ? (
              <>
                {canApply ? (
                  <label className="checkbox-field review-backup">
                    <input type="checkbox" checked={backupFirst} onChange={(e) => setBackupFirst(e.target.checked)} />
                    <span className="muted tiny">
                      {backupFirst
                        ? "Back up Mealie first (recommended). Only the items you selected change."
                        : "No backup first. Only the items you selected change."}
                      {deletes
                        ? " Removed recipes are kept in Library, Recently deleted, so you can restore them one by one."
                        : ""}
                      {!backupFirst && renames
                        ? deletes ? " Renames can't be undone from CookDex." : " They can't be undone from CookDex."
                        : ""}
                      {categorize ? " Recipes that changed since the preview are skipped." : ""}
                      {rulesLeftOut ? " Rule matches aren't part of this review; run Rules Only to add those." : ""}
                    </span>
                  </label>
                ) : (
                  <span className="muted tiny">An owner has to approve live changes for this task.</span>
                )}
                <button
                  type="button"
                  className="primary"
                  disabled={!canApply || nothingSelected || apply.isPending}
                  onClick={() => apply.mutate()}
                >
                  {apply.isPending ? "Starting…" : applyLabel(plan)}
                </button>
              </>
            ) : (
              <Dialog.Close className="ghost">Done</Dialog.Close>
            )}
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

const STATUS_COPY = {
  applied: { label: "Done", tone: "success" },
  error: { label: "Failed", tone: "danger" },
  skipped: { label: "Kept", tone: "neutral" },
  planned: { label: "Planned", tone: "neutral" },
};

function StatusChip({ status, skippedLabel }) {
  const copy =
    status === "skipped" && skippedLabel
      ? { ...STATUS_COPY.skipped, label: skippedLabel }
      : STATUS_COPY[status] || { label: status, tone: "neutral" };
  return <span className={`status-pill ${copy.tone}`}>{copy.label}</span>;
}

function LeaveButton({ name, disabled, onClick }) {
  return (
    <button
      type="button"
      className="ghost small review-leave"
      disabled={disabled}
      onClick={onClick}
      aria-label={`Leave ${name} as is`}
      title="Stop flagging this recipe. It's checked again if it changes in Mealie."
    >
      Leave as is
    </button>
  );
}

function LeaveAllButton({ count, disabled, onClick }) {
  return (
    <button
      type="button"
      className="ghost small review-leave-all"
      disabled={disabled}
      onClick={onClick}
      title="Stop flagging these recipes. Each is checked again if it changes in Mealie."
    >
      Leave all {count} as is
    </button>
  );
}
