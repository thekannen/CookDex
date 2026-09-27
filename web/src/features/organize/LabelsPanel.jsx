import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { describeChange } from "./model.mjs";
import StarterPacks, { SPARSE_BELOW } from "./StarterPacks";

const DEFAULT_COLOR = "#959595";

// Food labels group ingredients by aisle on shopping lists. Edits are staged
// with the rest of Organize and applied together.
export default function LabelsPanel({ staged, onStage, onUnstage }) {
  const labels = useQuery({
    queryKey: ["organize", "labels"],
    queryFn: () => api("/organize/labels", { timeout: 60000 }),
    staleTime: 30000,
  });
  const [adding, setAdding] = useState(false);
  const items = labels.data?.items || [];
  const created = Object.values(staged).filter((c) => c.kind === "labels" && c.op === "create");
  const targets = items.filter((item) => !["merge", "delete"].includes(staged[item.id]?.op));

  const starterPacks = (prominent) => (
    <StarterPacks
      kind="labels"
      noun={{ singular: "label", plural: "labels" }}
      existingNames={items.map((item) => item.name)}
      staged={staged}
      onStage={onStage}
      prominent={prominent}
    />
  );
  const sparse = Boolean(labels.data) && items.length < SPARSE_BELOW;

  return (
    <section className="cookbooks">
      {sparse ? starterPacks(true) : null}
      <div className="organize-toolbar">
        <span className="muted tiny">
          {labels.data
            ? `${items.length} labels. Labels group foods by aisle on shopping lists; the number is how many foods use each.`
            : ""}
        </span>
        <button type="button" className="ghost small" onClick={() => setAdding(true)} disabled={adding}>
          <Icon name="plus" /> New label
        </button>
        {labels.data && !sparse ? starterPacks(false) : null}
      </div>

      {labels.isLoading ? <p className="muted">Loading labels…</p> : null}
      {labels.isError ? (
        <p className="welcome-message error" role="alert"><Icon name="x-circle" /> {String(labels.error?.message || labels.error)}</p>
      ) : null}

      <div className="organize-table" role="table" aria-label="Labels">
        <div className="organize-row organize-row-head" role="row">
          <span role="columnheader">Label</span>
          <span role="columnheader" className="num">Foods</span>
          <span role="columnheader">Suggestion</span>
          <span role="columnheader" className="sr-only">Actions</span>
        </div>
        {adding ? (
          <LabelForm
            initial={{ name: "", color: DEFAULT_COLOR }}
            submitLabel="Stage"
            onCancel={() => setAdding(false)}
            onSubmit={(fields) => {
              onStage({ op: "create", kind: "labels", id: `new-${Date.now()}`, name: fields.name, to: fields });
              setAdding(false);
            }}
          />
        ) : null}
        {created.map((change) => (
          <div key={change.id} className="organize-row is-staged" role="row">
            <span role="cell" className="organize-name">
              <Swatch color={change.to.color} /> <strong>{change.to.name}</strong> <span className="staged-note">New</span>
            </span>
            <span role="cell" className="num">0</span>
            <span role="cell" />
            <span role="cell" className="organize-actions">
              <button type="button" className="ghost small" onClick={() => onUnstage(change.id)}>Undo</button>
            </span>
          </div>
        ))}
        {items.map((label) => (
          <LabelRow
            key={label.id}
            label={label}
            change={staged[label.id]}
            targets={targets.filter((t) => t.id !== label.id)}
            onStage={onStage}
            onUnstage={() => onUnstage(label.id)}
          />
        ))}
      </div>
    </section>
  );
}

function Swatch({ color }) {
  return <span className="label-swatch" style={{ background: color || DEFAULT_COLOR }} aria-hidden="true" />;
}

function LabelForm({ initial, submitLabel, onCancel, onSubmit }) {
  const [name, setName] = useState(initial.name);
  const [color, setColor] = useState(initial.color || DEFAULT_COLOR);
  return (
    <div className="organize-row" role="row">
      <form
        role="cell"
        className="inline-edit organize-name"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) onSubmit({ name: name.trim(), color });
        }}
      >
        <input type="color" aria-label="Label color" value={color} onChange={(e) => setColor(e.target.value)} className="label-color" />
        <input aria-label="Label name" value={name} autoFocus onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") onCancel(); }} />
        <button type="submit" className="primary small" disabled={!name.trim()}>{submitLabel}</button>
        <button type="button" className="ghost small" onClick={onCancel}>Cancel</button>
      </form>
    </div>
  );
}

function LabelRow({ label, change, targets, onStage, onUnstage }) {
  const [mode, setMode] = useState(""); // "", "edit", "merge"
  const [target, setTarget] = useState(label.merge_into?.id || "");

  if (change) {
    return (
      <div className={`organize-row is-staged staged-${change.op}`} role="row">
        <span role="cell" className="organize-name">
          <Swatch color={change.to?.color || label.color} /> <span className="old">{label.name}</span>
          <span className="staged-note">{change.op === "merge" ? `Merge into “${change.target_name}”` : describeChange(change, { short: true })}</span>
        </span>
        <span role="cell" className="num">{label.count}</span>
        <span role="cell" />
        <span role="cell" className="organize-actions">
          <button type="button" className="ghost small" onClick={onUnstage}>Undo</button>
        </span>
      </div>
    );
  }

  if (mode === "edit") {
    return (
      <LabelForm
        initial={label}
        submitLabel="Stage"
        onCancel={() => setMode("")}
        onSubmit={(fields) => {
          if (fields.name !== label.name || fields.color.toLowerCase() !== String(label.color).toLowerCase()) {
            onStage({ op: "update", kind: "labels", id: label.id, name: label.name, to: fields });
          }
          setMode("");
        }}
      />
    );
  }

  return (
    <div className="organize-row" role="row">
      <span role="cell" className="organize-name">
        {mode === "merge" ? (
          <form
            className="inline-edit"
            onSubmit={(e) => {
              e.preventDefault();
              const chosen = targets.find((t) => t.id === target);
              if (chosen) onStage({ op: "merge", kind: "labels", id: label.id, name: label.name, target_id: chosen.id, target_name: chosen.name });
              setMode("");
            }}
          >
            <span className="muted tiny">Move its foods to</span>
            <select aria-label={`Merge ${label.name} into`} value={target} onChange={(e) => setTarget(e.target.value)} autoFocus>
              <option value="">Choose…</option>
              {targets.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.count})</option>)}
            </select>
            <button type="submit" className="primary small" disabled={!target}>Stage</button>
            <button type="button" className="ghost small" onClick={() => setMode("")}>Cancel</button>
          </form>
        ) : (
          <>
            <Swatch color={label.color} /> <strong>{label.name}</strong>
          </>
        )}
      </span>
      <span role="cell" className={`num${label.count === 0 ? " muted" : ""}`}>{label.count}</span>
      <span role="cell" className="organize-suggestion">
        {label.merge_into ? (
          <>
            <span>Looks like “{label.merge_into.name}”</span>
            <button
              type="button"
              className="ghost small"
              onClick={() => onStage({ op: "merge", kind: "labels", id: label.id, name: label.name, target_id: label.merge_into.id, target_name: label.merge_into.name })}
            >
              Merge
            </button>
          </>
        ) : label.count === 0 ? (
          <span className="muted">No foods use it</span>
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
              title={label.count ? `${label.count} foods lose this label` : undefined}
              onClick={() => onStage({ op: "delete", kind: "labels", id: label.id, name: label.name })}
            >
              Delete
            </button>
          </>
        )}
      </span>
    </div>
  );
}
