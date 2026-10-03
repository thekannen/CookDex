import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { describeChange } from "./model.mjs";
import { aliasesToText, ingredientEdit, textToAliases } from "./ingredients.mjs";

const PAGE = 150;

const COPY = {
  foods: {
    noun: "food",
    title: "Foods",
    intro: "Foods are what the ingredient parser links each line to. Merging keeps the old name as an alias, so new recipes parse to the kept food.",
  },
  units: {
    noun: "unit",
    title: "Units",
    intro: "Merging keeps the old name as an alias, so “tbsp” and “Tbs” both parse to the kept unit.",
  },
};

// Ingredient foods or units. Edits are staged with the rest of Organize and
// applied together.
export default function IngredientsPanel({ kind, withLabels, staged, onStage, onUnstage, canApply, onNotice, onError }) {
  const copy = COPY[kind];
  const list = useQuery({
    queryKey: ["organize", kind],
    queryFn: () => api(`/organize/${kind}`, { timeout: 120000 }),
    staleTime: 30000,
  });
  const labels = useQuery({
    queryKey: ["organize", "labels"],
    queryFn: () => api("/organize/labels", { timeout: 60000 }),
    enabled: withLabels,
    staleTime: 30000,
  });
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [limit, setLimit] = useState(PAGE);
  const [adding, setAdding] = useState(false);

  const items = list.data?.items || [];
  const labelOptions = labels.data?.items || [];
  const counted = Boolean(list.data?.counted);
  const targets = items.filter((item) => !["merge", "delete"].includes(staged[item.id]?.op));
  const created = Object.values(staged).filter((c) => c.kind === kind && c.op === "create");
  const query = search.trim().toLowerCase();
  const visible = items.filter((item) => {
    if (query && ![item.name, item.plural_name, item.abbreviation, ...(item.aliases || [])].some((n) => n && n.toLowerCase().includes(query))) {
      return false;
    }
    if (filter === "suggested") return Boolean(item.merge_into);
    if (filter === "unused") return item.count === 0;
    if (filter === "unlabeled") return !item.label_id;
    return true;
  });

  const filters = [
    { id: "all", label: "All" },
    { id: "suggested", label: `Suggested merges${list.data ? ` (${list.data.suggested_merges})` : ""}` },
    ...(counted ? [{ id: "unused", label: `Unused${list.data ? ` (${list.data.unused})` : ""}` }] : []),
    ...(withLabels ? [{ id: "unlabeled", label: `No label${list.data ? ` (${list.data.unlabeled})` : ""}` }] : []),
  ];

  function stageMerge(item, target) {
    onStage({ op: "merge", kind, id: item.id, name: item.name, target_id: target.id, target_name: target.name });
  }
  function stageAllSuggestions() {
    for (const item of items) if (item.merge_into && !staged[item.id]) stageMerge(item, item.merge_into);
  }
  function stageAllUnused() {
    for (const item of items) {
      if (item.count === 0 && !staged[item.id]) onStage({ op: "delete", kind, id: item.id, name: item.name, unused: true });
    }
  }

  return (
    <section className="cookbooks">
      <p className="muted tiny">{copy.intro}</p>
      <div className="organize-toolbar">
        <input
          type="search"
          aria-label={`Search ${copy.title.toLowerCase()}`}
          placeholder={`Search ${copy.title.toLowerCase()} and aliases`}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setLimit(PAGE); }}
        />
        <div className="chip-row" role="group" aria-label="Show">
          {filters.map((option) => (
            <button
              key={option.id}
              type="button"
              className={`chip-btn${filter === option.id ? " active" : ""}`}
              aria-pressed={filter === option.id}
              onClick={() => { setFilter(option.id); setLimit(PAGE); }}
            >
              {option.label}
            </button>
          ))}
        </div>
        {filter === "suggested" && list.data?.suggested_merges ? (
          <button type="button" className="ghost small" onClick={stageAllSuggestions}>Merge all suggested</button>
        ) : null}
        {filter === "unused" && list.data?.unused && list.data.unused < items.length ? (
          <button type="button" className="ghost small" onClick={stageAllUnused}>Delete all unused</button>
        ) : null}
        {filter === "unused" && list.data?.unused && list.data.unused >= items.length ? (
          <span className="muted tiny">No recipe uses any {copy.title.toLowerCase()} yet, so none are suggested for removal.</span>
        ) : null}
        {kind === "units" ? (
          <button type="button" className="ghost small" onClick={() => setAdding(true)} disabled={adding}>
            <Icon name="plus" /> New unit
          </button>
        ) : null}
      </div>

      {!list.data && !list.isError ? <p className="muted">Loading {copy.title.toLowerCase()} and counting recipes…</p> : null}
      {list.isError ? (
        <p className="welcome-message error" role="alert"><Icon name="x-circle" /> {String(list.error?.message || list.error)}</p>
      ) : null}
      {list.data && !counted && items.length ? (
        <p className="muted tiny">There are too many {copy.title.toLowerCase()} to count recipes for each one.</p>
      ) : null}

      {list.data ? (
        <div className="organize-table" role="table" aria-label={copy.title}>
          <div className="organize-row organize-row-head" role="row">
            <span role="columnheader">{copy.noun}</span>
            <span role="columnheader" className="num">Recipes</span>
            <span role="columnheader">Suggestion</span>
            <span role="columnheader" className="sr-only">Actions</span>
          </div>
          {adding ? (
            <IngredientForm
              kind={kind}
              initial={{ name: "", plural_name: "", abbreviation: "", aliases: [] }}
              labelOptions={labelOptions}
              onCancel={() => setAdding(false)}
              onSubmit={(to) => {
                onStage({ op: "create", kind, id: `new-${Date.now()}`, name: to.name, to });
                setAdding(false);
              }}
            />
          ) : null}
          {created.map((change) => (
            <div key={change.id} className="organize-row is-staged" role="row">
              <span role="cell" className="organize-name">
                <strong>{change.to.name}</strong>
                {change.to.abbreviation ? <span className="muted"> ({change.to.abbreviation})</span> : null}
                <span className="staged-note">New</span>
              </span>
              <span role="cell" className="num">0</span>
              <span role="cell" />
              <span role="cell" className="organize-actions">
                <button type="button" className="ghost small" onClick={() => onUnstage(change.id)}>Undo</button>
              </span>
            </div>
          ))}
          {visible.length === 0 ? (
            items.length === 0 && created.length === 0 ? (
              <StandardList kind={kind} title={copy.title} canApply={canApply} onDone={() => list.refetch()} onNotice={onNotice} onError={onError} />
            ) : (
              <p className="muted organize-empty">{query ? `No ${copy.title.toLowerCase()} match “${query}”.` : "Nothing here right now."}</p>
            )
          ) : null}
          {visible.slice(0, limit).map((item) => (
            <IngredientRow
              key={item.id}
              kind={kind}
              noun={copy.noun}
              item={item}
              change={staged[item.id]}
              targets={targets}
              labelOptions={labelOptions}
              withLabels={withLabels}
              onStage={onStage}
              onMerge={(target) => stageMerge(item, target)}
              onUnstage={() => onUnstage(item.id)}
            />
          ))}
        </div>
      ) : null}
      {visible.length > limit ? (
        <button type="button" className="ghost small" onClick={() => setLimit(limit + PAGE)}>
          Show more ({visible.length - limit} left)
        </button>
      ) : null}
    </section>
  );
}

function Names({ kind, item }) {
  const extra = [
    kind === "units" && item.abbreviation ? item.abbreviation : "",
    item.plural_name && item.plural_name !== item.name ? item.plural_name : "",
    ...(item.aliases || []),
  ].filter(Boolean);
  return extra.length ? <span className="ingredient-aliases muted">{extra.join(" · ")}</span> : null;
}

function LabelChip({ label }) {
  if (!label) return null;
  return (
    <span className="ingredient-label">
      <span className="label-swatch" style={{ background: label.color }} aria-hidden="true" /> {label.name}
    </span>
  );
}

function IngredientForm({ kind, initial, labelOptions, withLabels, onCancel, onSubmit }) {
  const [name, setName] = useState(initial.name || "");
  const [plural, setPlural] = useState(initial.plural_name || "");
  const [abbreviation, setAbbreviation] = useState(initial.abbreviation || "");
  const [labelId, setLabelId] = useState(initial.label_id || "");
  const [aliases, setAliases] = useState(aliasesToText(initial.aliases));
  const noun = kind === "foods" ? "food" : "unit";

  return (
    <div className="organize-row" role="row">
      <form
        role="cell"
        className="inline-edit ingredient-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) return;
          const to = { name: name.trim(), plural_name: plural.trim(), aliases: textToAliases(aliases, name) };
          if (kind === "foods") to.label_id = labelId;
          else to.abbreviation = abbreviation.trim();
          onSubmit(to);
        }}
        onKeyDown={(e) => { if (e.key === "Escape") onCancel(); }}
      >
        <label>
          <span>Name</span>
          <input value={name} autoFocus onChange={(e) => setName(e.target.value)} aria-label={`${noun} name`} />
        </label>
        {kind === "units" ? (
          <label className="narrow">
            <span>Abbreviation</span>
            <input value={abbreviation} onChange={(e) => setAbbreviation(e.target.value)} placeholder="tbsp" />
          </label>
        ) : null}
        <label>
          <span>Plural</span>
          <input value={plural} onChange={(e) => setPlural(e.target.value)} />
        </label>
        {kind === "foods" && withLabels ? (
          <label>
            <span>Label</span>
            <select value={labelId} onChange={(e) => setLabelId(e.target.value)}>
              <option value="">No label</option>
              {labelOptions.map((label) => <option key={label.id} value={label.id}>{label.name}</option>)}
            </select>
          </label>
        ) : null}
        <label className="wide">
          <span>Aliases, comma-separated</span>
          <input value={aliases} onChange={(e) => setAliases(e.target.value)} placeholder={kind === "units" ? "Tbs, T" : "scallion, spring onion"} />
        </label>
        <div className="ingredient-form-actions">
          <button type="submit" className="primary small" disabled={!name.trim()}>Stage</button>
          <button type="button" className="ghost small" onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </div>
  );
}

function IngredientRow({ kind, noun, item, change, targets, labelOptions, withLabels, onStage, onMerge, onUnstage }) {
  const [mode, setMode] = useState(""); // "", "edit", "merge"
  const [target, setTarget] = useState(item.merge_into?.id || "");
  const label = item.label;

  if (change) {
    const nextLabel = change.op === "update" && kind === "foods"
      ? labelOptions.find((l) => l.id === change.to.label_id)
      : null;
    return (
      <div className={`organize-row is-staged staged-${change.op}`} role="row">
        <span role="cell" className="organize-name">
          <span className="old">{item.name}</span>
          <span className="staged-note">{describeChange(change, { short: true })}</span>
          {nextLabel && nextLabel.id !== item.label_id ? <LabelChip label={nextLabel} /> : null}
        </span>
        <span role="cell" className="num">{item.count ?? "–"}</span>
        <span role="cell" />
        <span role="cell" className="organize-actions">
          <button type="button" className="ghost small" onClick={onUnstage}>Undo</button>
        </span>
      </div>
    );
  }

  if (mode === "edit") {
    return (
      <IngredientForm
        kind={kind}
        initial={item}
        labelOptions={labelOptions}
        withLabels={withLabels}
        onCancel={() => setMode("")}
        onSubmit={(to) => {
          const edit = ingredientEdit(kind, item, to);
          if (edit) onStage(edit);
          setMode("");
        }}
      />
    );
  }

  const inUse = item.count > 0;
  return (
    <div className="organize-row" role="row">
      <span role="cell" className="organize-name">
        {mode === "merge" ? (
          <form
            className="inline-edit"
            onSubmit={(e) => {
              e.preventDefault();
              const chosen = targets.find((t) => t.id === target);
              if (chosen) onMerge(chosen);
              setMode("");
            }}
          >
            <span className="muted tiny">Merge “{item.name}” into</span>
            <select aria-label={`Merge ${item.name} into`} value={target} onChange={(e) => setTarget(e.target.value)} autoFocus>
              <option value="">Choose…</option>
              {targets.filter((t) => t.id !== item.id).map((t) => (
                <option key={t.id} value={t.id}>{t.name}{t.count != null ? ` (${t.count})` : ""}</option>
              ))}
            </select>
            <button type="submit" className="primary small" disabled={!target}>Stage</button>
            <button type="button" className="ghost small" onClick={() => setMode("")}>Cancel</button>
          </form>
        ) : (
          <>
            <strong>{item.name}</strong> <Names kind={kind} item={item} />
            {withLabels ? <LabelChip label={label} /> : null}
          </>
        )}
      </span>
      <span role="cell" className={`num${item.count === 0 ? " muted" : ""}`}>{item.count ?? "–"}</span>
      <span role="cell" className="organize-suggestion">
        {item.merge_into ? (
          <>
            <span>Looks like “{item.merge_into.name}”</span>
            <button type="button" className="ghost small" onClick={() => onMerge(item.merge_into)}>Merge</button>
          </>
        ) : item.count === 0 ? (
          <span className="muted">Not used by any recipe</span>
        ) : null}
      </span>
      <span role="cell" className="organize-actions">
        {mode ? null : (
          <>
            <button type="button" className="ghost small" onClick={() => setMode("edit")}>Edit</button>
            <button type="button" className="ghost small" onClick={() => setMode("merge")}>Merge…</button>
            <button
              type="button"
              className="ghost small danger-text"
              disabled={inUse}
              title={inUse ? `${item.count} recipes use this ${noun}. Merge it into another instead.` : undefined}
              onClick={() => onStage({ op: "delete", kind, id: item.id, name: item.name, unused: item.count === 0 })}
            >
              Delete
            </button>
          </>
        )}
      </span>
    </div>
  );
}

// An empty foods or units list: offer Mealie's own standard list, which is
// what ingredient linking needs to match lines like "2 cups flour".
function StandardList({ kind, title, canApply, onDone, onNotice, onError }) {
  const [busy, setBusy] = useState(false);
  const lower = title.toLowerCase();
  async function add() {
    setBusy(true);
    try {
      const result = await api(`/organize/standard/${kind}`, {
        method: "POST",
        body: { locale: (navigator.language || "en-US").replace("_", "-") },
        timeout: 320000,
      });
      onNotice?.(`Added ${result.added.toLocaleString()} standard ${lower} (${result.locale}).`);
      onDone();
    } catch (exc) {
      onError?.(exc);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="starter-card organize-empty">
      <div>
        <strong>Mealie has no {lower} yet</strong>
        <p className="muted tiny">
          Mealie comes with a standard list of common {lower} in your language. Linking ingredients needs them to
          understand lines like “2 cups flour”. Adding them changes no recipes.
        </p>
      </div>
      <button type="button" className="primary small" onClick={add} disabled={busy || !canApply} title={canApply ? "" : "An owner has to approve changes from Organize first."}>
        <Icon name="plus" /> {busy ? "Adding…" : `Add Mealie's standard ${lower}`}
      </button>
    </div>
  );
}
