import React, { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { createChange, packItems } from "./packs.mjs";

// Few items of a kind -> a prominent card; otherwise a small toolbar button.
export const SPARSE_BELOW = 10;

function usePacks() {
  return useQuery({
    queryKey: ["organize", "starter-packs"],
    queryFn: () => api("/organize/starter-packs"),
    staleTime: Infinity,
  });
}

// "Start from a suggested set": pick items from curated packs and stage them
// as new tags, categories, tools or labels.
export default function StarterPacks({ kind, noun, existingNames, staged, onStage, prominent, count = 0 }) {
  const packs = usePacks();
  const [open, setOpen] = useState(false);
  const forKind = (packs.data?.packs || []).filter((pack) => pack.kind === kind);
  if (!forKind.length) return null;

  const trigger = (
    <button type="button" className={prominent ? "primary small" : "ghost small"} onClick={() => setOpen(true)}>
      <Icon name="plus" /> {prominent ? "Choose a starter set" : "Starter sets"}
    </button>
  );

  return (
    <>
      {prominent ? (
        <div className="starter-card">
          <div>
            <strong>Start from a suggested set</strong>
            <p className="muted tiny">
              {count ? `Only a few ${noun.plural} so far.` : `No ${noun.plural} yet.`} Pick from sets like {forKind.map((p) => p.title.toLowerCase()).join(", ")}, then
              review and apply them with your other changes.
            </p>
          </div>
          {trigger}
        </div>
      ) : (
        trigger
      )}
      {open ? (
        <PackDialog
          kind={kind}
          noun={noun}
          packs={forKind}
          existingNames={existingNames}
          staged={staged}
          onStage={onStage}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}

function PackDialog({ kind, noun, packs, existingNames, staged, onStage, onClose }) {
  const stagedNames = Object.values(staged).filter((c) => c.kind === kind && c.op === "create").map((c) => c.name);
  const byPack = useMemo(
    () => packs.map((pack) => ({ pack, items: packItems(pack, existingNames, stagedNames) })),
    // Computed once per opening, so staging from here doesn't reshuffle the list.
    [packs]
  );
  const [picked, setPicked] = useState(
    () => new Set(byPack.flatMap(({ items }) => items.filter((i) => i.state === "new").map((i) => i.name)))
  );
  const [chosenPacks, setChosenPacks] = useState(() => new Set(byPack.length === 1 ? [byPack[0].pack.id] : []));

  const chosen = byPack
    .filter(({ pack }) => chosenPacks.has(pack.id))
    .flatMap(({ items }) => items.filter((i) => i.state === "new" && picked.has(i.name)));
  // One entry per name, in case two packs share an item.
  const toStage = [...new Map(chosen.map((item) => [item.name.toLowerCase(), item])).values()];

  function toggle(set, setter, value) {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    setter(next);
  }

  return (
    <Dialog.Root open onOpenChange={(value) => { if (!value) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="review-sheet" aria-describedby="starter-desc">
          <header className="review-sheet-head">
            <div>
              <Dialog.Title className="review-sheet-title">Starter {noun.plural}</Dialog.Title>
              <Dialog.Description id="starter-desc" className="muted">
                Choose a set, untick anything you don't want, and stage the rest. Ones you already have are left out.
              </Dialog.Description>
            </div>
            <Dialog.Close className="ghost small" aria-label="Close"><Icon name="x" /></Dialog.Close>
          </header>
          <div className="review-sheet-body">
            {byPack.map(({ pack, items }) => {
              const fresh = items.filter((i) => i.state === "new");
              const isOn = chosenPacks.has(pack.id);
              return (
                <section key={pack.id} className={`starter-pack${isOn ? " is-on" : ""}`}>
                  <label className="starter-pack-head">
                    <input
                      type="checkbox"
                      checked={isOn}
                      disabled={!fresh.length}
                      onChange={() => toggle(chosenPacks, setChosenPacks, pack.id)}
                    />
                    <span>
                      <strong>{pack.title}</strong>
                      <span className="muted tiny">
                        {" "}{pack.description} {fresh.length ? `${fresh.length} new` : "You have all of these."}
                      </span>
                    </span>
                  </label>
                  {isOn ? (
                    <div className="starter-items">
                      {items.map((item) => (
                        <label key={item.name} className={`starter-item state-${item.state}`}>
                          <input
                            type="checkbox"
                            checked={item.state === "new" ? picked.has(item.name) : true}
                            disabled={item.state !== "new"}
                            onChange={() => toggle(picked, setPicked, item.name)}
                          />
                          {item.color ? <span className="label-swatch" style={{ background: item.color }} aria-hidden="true" /> : null}
                          {item.name}
                          {item.state === "have" ? <span className="muted tiny"> (have it)</span> : null}
                          {item.state === "staged" ? <span className="muted tiny"> (staged)</span> : null}
                        </label>
                      ))}
                    </div>
                  ) : null}
                </section>
              );
            })}
          </div>
          <footer className="review-sheet-foot">
            <span className="muted tiny">Nothing changes until you apply.</span>
            <button
              type="button"
              className="primary"
              disabled={!toStage.length}
              onClick={() => {
                for (const item of toStage) onStage(createChange(kind, item));
                onClose();
              }}
            >
              Stage {toStage.length} new {toStage.length === 1 ? noun.singular : noun.plural}
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
