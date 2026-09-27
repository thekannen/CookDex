import React, { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import {
  DELETE_GROUP_COPY,
  REVIEWABLE_TASKS,
  applyLabel,
  applyOptions,
  buildPlan,
  collectItems,
  defaultSelection,
  describeResult,
  hasItems,
  planSize,
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

  const preview = run.options?.dry_run !== false;
  const reviewable = preview && run.status === "succeeded" && REVIEWABLE_TASKS.has(run.task_id);

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
        taskTitle={taskTitle}
        collected={collected}
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
  const plan = useMemo(() => buildPlan(collected, selected, editedNames), [collected, selected, editedNames]);
  const { deletes, renames } = planSize(plan);
  const nothingSelected = deletes + renames === 0;

  const apply = useMutation({
    mutationFn: () =>
      api("/runs", {
        method: "POST",
        body: { task_id: run.task_id, options: applyOptions(run.options, plan), confirmed: true },
      }),
    onSuccess: (newRun) => {
      queryClient.invalidateQueries({ queryKey: ["run-result"] });
      onOpenChange(false);
      onApplied?.(newRun);
    },
    onError: (exc) => onError?.(exc),
  });

  function toggle(key) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const deleteGroups = Object.entries(collected.deleteGroups).filter(([, items]) => items.length > 0);

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
                  ? "Untick anything you want to keep. You can edit a new name before applying."
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
                            {group === "duplicate" && item.keep_name ? `Keeps "${item.keep_name}"` : item.reason}
                            {item.error ? ` · ${item.error}` : ""}
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}

            {collected.renames.length > 0 && (
              <section className="review-group">
                <h4>
                  Names to clean up <span className="review-count">{collected.renames.length}</span>
                </h4>
                <ul className="review-list">
                  {collected.renames.map((item) => {
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
                <span className="muted tiny">
                  {canApply
                    ? "A Mealie backup is made first. Only the items you selected change."
                    : "An owner has to approve live changes for this task."}
                </span>
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

function StatusChip({ status }) {
  const copy = STATUS_COPY[status] || { label: status, tone: "neutral" };
  return <span className={`status-pill ${copy.tone}`}>{copy.label}</span>;
}
