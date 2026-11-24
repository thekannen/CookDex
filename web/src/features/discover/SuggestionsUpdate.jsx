import React, { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import SelectAllToggle from "../../components/SelectAllToggle";
import { api } from "../../utils.jsx";

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function summary(update) {
  const parts = [];
  if (update.new.length) parts.push(`${plural(update.new.length, "new suggested source")} to add`);
  if (update.retired.length) parts.push(`${update.retired.length} of your sources ${update.retired.length === 1 ? "isn't" : "aren't"} suggested any more`);
  return parts.join(" · ");
}

// The suggested sources changed since this install last looked. Nothing
// changes until someone chooses: new sources are added switched off, and
// retired ones are only removed if ticked.
export default function SuggestionsUpdate({ update, onNotice, onError }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const newKeys = update.new.map((item) => `new:${item.url}`);
  const retiredKeys = update.retired.map((item) => `retired:${item.id}`);
  const [selected, setSelected] = useState(() => new Set([...newKeys, ...retiredKeys]));

  const apply = useMutation({
    mutationFn: (body) => api("/discover/suggestions", { method: "POST", body }),
    onSuccess: (result, body) => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["discover"] });
      if (body.add.length || body.remove_ids.length) {
        const done = [];
        if (result.added) done.push(`Added ${plural(result.added, "source")}, switched off`);
        if (result.removed) done.push(`removed ${plural(result.removed, "source")}`);
        onNotice?.(done.length ? `${done.join(" and ")}.` : "Sources updated.");
      }
    },
    onError: (exc) => onError?.(exc),
  });

  const toggle = (key) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const adding = update.new.filter((item) => selected.has(`new:${item.url}`));
  const removing = update.retired.filter((item) => selected.has(`retired:${item.id}`));
  const label = [adding.length ? `Add ${adding.length}` : "", removing.length ? `remove ${removing.length}` : ""]
    .filter(Boolean)
    .join(", ");

  return (
    <>
      <div className="library-banner discover-update" role="status">
        <span><Icon name="sparkles" /> Suggested sources were updated: {summary(update)}.</span>
        <span className="discover-update-actions">
          <button type="button" className="ghost small" onClick={() => setOpen(true)}>Review</button>
          <button
            type="button"
            className="ghost small"
            disabled={apply.isPending}
            onClick={() => apply.mutate({ add: [], remove_ids: [] })}
            title="Keep your sources as they are and hide this"
          >
            Dismiss
          </button>
        </span>
      </div>

      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="sheet-overlay" />
          <Dialog.Content className="review-sheet" aria-describedby="suggestions-update-desc">
            <header className="review-sheet-head">
              <div>
                <Dialog.Title className="review-sheet-title">Update your suggested sources</Dialog.Title>
                <Dialog.Description id="suggestions-update-desc" className="muted">
                  We re-read the terms of every suggested site and took off the ones that don't allow automated visits.
                  Choose what to change. Anything you leave unticked stays as it is.
                </Dialog.Description>
              </div>
            </header>
            <div className="review-sheet-body">
              {update.retired.length ? (
                <section className="review-group">
                  <h4>
                    No longer suggested <span className="review-count">{update.retired.length}</span>
                    <SelectAllToggle keys={retiredKeys} selected={selected} onChange={setSelected} label="No longer suggested" />
                  </h4>
                  <p className="muted tiny">Ticked sources are removed. Recipes already imported from them stay in Mealie.</p>
                  <ul className="review-list">
                    {update.retired.map((item) => {
                      const key = `retired:${item.id}`;
                      return (
                        <li key={key} className={`review-row${selected.has(key) ? "" : " is-kept"}`}>
                          <input type="checkbox" id={`suggest-${key}`} checked={selected.has(key)} onChange={() => toggle(key)} />
                          <label htmlFor={`suggest-${key}`} className="review-row-main">
                            <strong>{item.label}</strong>
                            <span className="muted tiny">
                              {item.reason_text}
                              {item.moved_to ? ` It's now ${item.moved_to.replace(/^https?:\/\/(www\.)?/, "")}, listed below.` : ""}
                            </span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null}
              {update.new.length ? (
                <section className="review-group">
                  <h4>
                    New suggestions <span className="review-count">{update.new.length}</span>
                    <SelectAllToggle keys={newKeys} selected={selected} onChange={setSelected} label="New suggestions" />
                  </h4>
                  <p className="muted tiny">Added switched off, so nothing is visited until you turn a source on.</p>
                  <ul className="review-list">
                    {update.new.map((item) => {
                      const key = `new:${item.url}`;
                      return (
                        <li key={key} className={`review-row${selected.has(key) ? "" : " is-kept"}`}>
                          <input type="checkbox" id={`suggest-${key}`} checked={selected.has(key)} onChange={() => toggle(key)} />
                          <label htmlFor={`suggest-${key}`} className="review-row-main">
                            <strong>{item.label}</strong>
                            <span className="muted tiny">{item.group}</span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null}
            </div>
            <footer className="review-sheet-foot">
              <Dialog.Close className="ghost">Cancel</Dialog.Close>
              <button
                type="button"
                className="primary"
                disabled={apply.isPending}
                onClick={() =>
                  apply.mutate({ add: adding.map((item) => item.url), remove_ids: removing.map((item) => item.id) })
                }
              >
                {apply.isPending ? "Saving…" : label ? label.charAt(0).toUpperCase() + label.slice(1) : "Keep everything as it is"}
              </button>
            </footer>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
