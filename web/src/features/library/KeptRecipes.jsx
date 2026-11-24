import React, { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";

const KIND_LABELS = {
  junk: "Isn't a recipe",
  review: "Might not be a recipe",
  rename: "Name could be cleaner",
  name_clash: "Cleaned-up name matches another recipe",
};

// Recipes someone chose to leave as they are. Cleanups skip them, and the
// Library doesn't flag them, until they change in Mealie or are checked again here.
export default function KeptRecipes({ count, onError }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const kept = useQuery({ queryKey: ["library-kept"], queryFn: () => api("/library/kept"), enabled: open });
  const items = kept.data?.items || [];

  const forget = useMutation({
    mutationFn: (slugs) => api("/library/kept/forget", { method: "POST", body: { slugs } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["library-kept"] });
      queryClient.invalidateQueries({ queryKey: ["library"] });
    },
    onError: (exc) => onError?.(exc),
  });

  if (!count) return null;
  return (
    <>
      <button type="button" className="link-inline library-kept-link" onClick={() => setOpen(true)}>
        {count} recipe{count === 1 ? "" : "s"} left as is
      </button>
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="sheet-overlay" />
          <Dialog.Content className="review-sheet review-sheet-small" aria-describedby="kept-desc">
            <header className="review-sheet-head">
              <div>
                <Dialog.Title className="review-sheet-title">Left as is</Dialog.Title>
                <Dialog.Description id="kept-desc" className="muted">
                  Cleanups skip these recipes and the Library doesn't flag them. One that changes in Mealie is checked
                  again on its own. Check one again now to see it on the next scan.
                </Dialog.Description>
              </div>
              <Dialog.Close className="ghost small" aria-label="Close">
                <Icon name="x" />
              </Dialog.Close>
            </header>
            <div className="review-sheet-body">
              {kept.isLoading ? <p className="muted">Loading…</p> : null}
              <ul className="review-list">
                {items.map((item) => (
                  <li key={item.slug} className="review-row">
                    <span />
                    <span className="review-row-main">
                      <strong>{item.name || item.slug}</strong>
                      <span className="muted tiny">
                        {KIND_LABELS[item.kind] || "Left as is"}
                        {item.at ? ` · ${formatDistanceToNow(new Date(item.at), { addSuffix: true })}` : ""}
                        {item.by ? ` by ${item.by}` : ""}
                      </span>
                    </span>
                    <button
                      type="button"
                      className="ghost small review-leave"
                      disabled={forget.isPending}
                      onClick={() => forget.mutate([item.slug])}
                    >
                      Check again
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <footer className="review-sheet-foot">
              <Dialog.Close className="ghost">Close</Dialog.Close>
              {items.length > 1 ? (
                <button
                  type="button"
                  className="ghost"
                  disabled={forget.isPending}
                  onClick={() => forget.mutate(items.map((item) => item.slug))}
                >
                  Check all {items.length} again
                </button>
              ) : null}
            </footer>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
