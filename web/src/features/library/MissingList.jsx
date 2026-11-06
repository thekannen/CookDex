import React, { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import LoadError from "../../components/LoadError";
import { api } from "../../utils.jsx";

// How many rows to draw at once; a search narrows a long list.
const SHOWN = 300;

const TITLES = {
  yield: "Recipes missing servings",
  category: "Recipes with no category",
  ingredients: "Recipes with unlinked ingredients",
};

export function filterRecipes(recipes, search) {
  const needle = search.trim().toLowerCase();
  if (!needle) return recipes;
  return recipes.filter((recipe) => recipe.name.toLowerCase().includes(needle));
}

// The recipes the latest scan found missing one thing, each linking to the
// recipe in Mealie so it can be fixed there.
export default function MissingList({ dimension, onClose }) {
  const [search, setSearch] = useState("");
  const list = useQuery({
    queryKey: ["library-missing", dimension],
    queryFn: () => api(`/library/missing/${encodeURIComponent(dimension)}`),
  });
  const recipes = list.data?.recipes || [];
  const matches = useMemo(() => filterRecipes(recipes, search), [recipes, search]);
  const shown = matches.slice(0, SHOWN);
  const linked = recipes.some((recipe) => recipe.url);

  return (
    <Dialog.Root open onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="review-sheet review-sheet-small" aria-describedby="missing-list-desc">
          <header className="review-sheet-head">
            <div>
              <Dialog.Title className="review-sheet-title">{TITLES[dimension] || "Recipes"}</Dialog.Title>
              <Dialog.Description id="missing-list-desc" className="muted">
                {linked
                  ? "From your last scan. Open one to fix it in Mealie, then scan again to update the list."
                  : "From your last scan. Fix these in Mealie, then scan again to update the list."}
              </Dialog.Description>
            </div>
            <Dialog.Close className="ghost small" aria-label="Close">
              <Icon name="x" />
            </Dialog.Close>
          </header>
          <div className="review-sheet-body">
            {list.isLoading ? (
              <p className="muted">Loading…</p>
            ) : list.isError ? (
              <LoadError error={list.error} onRetry={() => list.refetch()} />
            ) : (
              <>
                {recipes.length > 10 ? (
                  <input
                    type="search"
                    className="missing-search"
                    placeholder={`Search ${recipes.length} recipes`}
                    aria-label="Search recipes"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                ) : null}
                {shown.length === 0 ? (
                  <p className="muted">{recipes.length ? "No recipes match." : "None left. Nice work."}</p>
                ) : (
                  <ul className="review-list missing-list">
                    {shown.map((recipe) => (
                      <li key={recipe.slug} className="missing-row">
                        {recipe.url ? (
                          <a href={recipe.url} target="_blank" rel="noopener noreferrer">
                            <span>{recipe.name}</span>
                            <Icon name="external" />
                          </a>
                        ) : (
                          <span>{recipe.name}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {matches.length > shown.length ? (
                  <p className="muted tiny">Showing {shown.length} of {matches.length}. Search to find others.</p>
                ) : null}
              </>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
