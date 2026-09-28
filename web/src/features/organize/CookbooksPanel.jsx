import React, { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { RULE_FIELDS, RULE_OPERATORS, buildRule, describeRows, parseRule, rowsToIds } from "./cookbooks.mjs";
import { describeChange } from "./model.mjs";

function useTerms(kind) {
  return useQuery({
    queryKey: ["organize", kind],
    queryFn: () => api(`/organize/${kind}`, { timeout: 60000 }),
    staleTime: 30000,
  });
}

// Cookbooks, edited in the recipe manager itself. Edits are staged with the
// rest of Organize and applied together.
export default function CookbooksPanel({ label, staged, onStage, onUnstage }) {
  const cookbooks = useQuery({
    queryKey: ["organize", "cookbooks"],
    queryFn: () => api("/organize/cookbooks", { timeout: 60000 }),
    staleTime: 30000,
  });
  const tags = useTerms("tags");
  const categories = useTerms("categories");
  const tools = useTerms("tools");
  const lookups = useMemo(
    () => ({ tags: tags.data?.items || [], categories: categories.data?.items || [], tools: tools.data?.items || [] }),
    [tags.data, categories.data, tools.data]
  );
  const [editing, setEditing] = useState(null); // existing cookbook, or {} for a new one

  const items = cookbooks.data?.items || [];
  const created = Object.values(staged).filter((c) => c.kind === "cookbooks" && c.op === "create");

  return (
    <section className="cookbooks">
      <div className="organize-toolbar">
        <span className="muted tiny">
          {cookbooks.data ? `${items.length} ${label.toLowerCase()}. Each one shows the recipes its filter matches.` : ""}
        </span>
        <button type="button" className="ghost small" onClick={() => setEditing({})}>
          <Icon name="plus" /> New {label.toLowerCase().replace(/s$/, "")}
        </button>
      </div>

      {!cookbooks.data && !cookbooks.isError ? <p className="muted">Loading {label.toLowerCase()}…</p> : null}
      {cookbooks.isError ? (
        <p className="welcome-message error" role="alert"><Icon name="x-circle" /> {String(cookbooks.error?.message || cookbooks.error)}</p>
      ) : null}

      <ul className="cookbook-list">
        {created.map((change) => (
          <li key={change.id} className="cookbook is-staged staged-create">
            <div className="cookbook-main">
              <strong>{change.to.name}</strong>
              <span className="staged-note">New</span>
              <RuleSummary rule={change.to.rule} lookups={lookups} />
            </div>
            <div className="organize-actions">
              <button type="button" className="ghost small" onClick={() => onUnstage(change.id)}>Undo</button>
            </div>
          </li>
        ))}
        {items.map((cookbook) => {
          const change = staged[cookbook.id];
          return (
            <li key={cookbook.id} className={`cookbook${change ? ` is-staged staged-${change.op}` : ""}`}>
              <div className="cookbook-main">
                <div className="cookbook-title">
                  <strong className="old">{cookbook.name}</strong>
                  {change ? <span className="staged-note">{describeChange(change, { short: true })}</span> : null}
                  {cookbook.public ? <span className="status-pill neutral">Public</span> : null}
                </div>
                {cookbook.description ? <span className="muted tiny">{cookbook.description}</span> : null}
                <RuleSummary rule={change?.to?.rule ?? cookbook.rule} lookups={lookups} />
              </div>
              <span className={`cookbook-matches${cookbook.matches === 0 ? " is-empty" : ""}`}>
                {cookbook.error ? "Filter error" : cookbook.matches === null ? "" : `${cookbook.matches} recipe${cookbook.matches === 1 ? "" : "s"}`}
              </span>
              <div className="organize-actions">
                {change ? (
                  <button type="button" className="ghost small" onClick={() => onUnstage(cookbook.id)}>Undo</button>
                ) : (
                  <>
                    <button type="button" className="ghost small" onClick={() => setEditing(cookbook)}>Edit</button>
                    <button
                      type="button"
                      className="ghost small danger-text"
                      onClick={() => onStage({ op: "delete", kind: "cookbooks", id: cookbook.id, name: cookbook.name })}
                    >
                      Delete
                    </button>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {editing ? (
        <CookbookEditor
          cookbook={editing}
          label={label}
          lookups={lookups}
          nextPosition={items.length + created.length + 1}
          onCancel={() => setEditing(null)}
          onSave={(change) => {
            onStage(change);
            setEditing(null);
          }}
        />
      ) : null}
    </section>
  );
}

function RuleSummary({ rule, lookups }) {
  const parsed = parseRule(rule);
  if (!String(rule || "").trim()) return <span className="muted tiny">No filter: matches nothing yet.</span>;
  if (!parsed.editable) return <code className="rule-raw">{rule}</code>;
  return (
    <span className="rule-summary">
      {describeRows(parsed.rows, lookups).map((row, index) => (
        <span key={index} className="rule-clause">
          {index > 0 ? <span className="muted">and</span> : null}
          <span className="muted">{row.field} {row.operator}</span>
          {row.values.map((value, i) => (
            <span key={i} className={`filter-chip${value.missing ? " missing" : ""}`}>{value.label}</span>
          ))}
        </span>
      ))}
    </span>
  );
}

function CookbookEditor({ cookbook, label, lookups, nextPosition, onCancel, onSave }) {
  const isNew = !cookbook.id;
  const parsed = useMemo(() => parseRule(cookbook.rule || ""), [cookbook.rule]);
  const [name, setName] = useState(cookbook.name || "");
  const [description, setDescription] = useState(cookbook.description || "");
  const [isPublic, setIsPublic] = useState(Boolean(cookbook.public));
  const [raw, setRaw] = useState(!parsed.editable);
  const [rawRule, setRawRule] = useState(cookbook.rule || "");
  const [rows, setRows] = useState(() =>
    parsed.editable && parsed.rows.length
      ? rowsToIds(parsed.rows, lookups)
      : [{ field: "categories", operator: "IN", identifier: "id", values: [] }]
  );
  const rule = raw ? rawRule.trim() : buildRule(rows);

  // Live count of the recipes the filter matches, debounced while typing.
  const [preview, setPreview] = useState(null);
  useEffect(() => {
    if (!rule) {
      setPreview({ matches: 0, sample: [], error: "" });
      return undefined;
    }
    const timer = setTimeout(() => {
      api("/organize/cookbooks/preview", { method: "POST", body: { rule } })
        .then(setPreview)
        .catch((exc) => setPreview({ matches: null, sample: [], error: String(exc?.message || exc) }));
    }, 400);
    return () => clearTimeout(timer);
  }, [rule]);

  function updateRow(index, patch) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  const singular = label.toLowerCase().replace(/s$/, "");
  const canSave = name.trim() && !preview?.error;

  return (
    <Dialog.Root open onOpenChange={(open) => { if (!open) onCancel(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="review-sheet" aria-describedby="cookbook-editor-desc">
          <header className="review-sheet-head">
            <div>
              <Dialog.Title className="review-sheet-title">{isNew ? `New ${singular}` : `Edit “${cookbook.name}”`}</Dialog.Title>
              <Dialog.Description id="cookbook-editor-desc" className="muted">
                A {singular} shows every recipe that matches its filter. Nothing changes until you apply.
              </Dialog.Description>
            </div>
            <Dialog.Close className="ghost small" aria-label="Close"><Icon name="x" /></Dialog.Close>
          </header>

          <div className="review-sheet-body cookbook-editor">
            <div className="welcome-field">
              <label htmlFor="cookbook-name">Name</label>
              <input id="cookbook-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="welcome-field">
              <label htmlFor="cookbook-description">Description</label>
              <input id="cookbook-description" value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <label className="switch">
              <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} />
              <span>Public: visible to people who aren't signed in to Mealie</span>
            </label>

            <section className="review-group">
              <h4>Recipes that match</h4>
              {raw ? (
                <>
                  {!parsed.editable ? (
                    <p className="muted tiny">This filter uses conditions the editor can't show, so it's edited as text.</p>
                  ) : null}
                  <textarea
                    aria-label="Filter"
                    className="rule-textarea"
                    rows={3}
                    value={rawRule}
                    onChange={(e) => setRawRule(e.target.value)}
                  />
                </>
              ) : (
                <div className="rule-rows">
                  {rows.map((row, index) => (
                    <RuleRow
                      key={index}
                      row={row}
                      first={index === 0}
                      terms={lookups[row.field] || []}
                      onChange={(patch) => updateRow(index, patch)}
                      onRemove={rows.length > 1 ? () => setRows((prev) => prev.filter((_, i) => i !== index)) : null}
                    />
                  ))}
                  <button
                    type="button"
                    className="ghost small"
                    onClick={() => setRows((prev) => [...prev, { field: "tags", operator: "IN", identifier: "id", values: [] }])}
                  >
                    <Icon name="plus" /> Add a condition
                  </button>
                </div>
              )}
              <p className={`rule-preview${preview?.error ? " error" : ""}`} role="status">
                {preview === null
                  ? "Counting…"
                  : preview.error
                    ? preview.error
                    : `${preview.matches} recipe${preview.matches === 1 ? "" : "s"} match${preview.matches === 1 ? "es" : ""}${preview.sample?.length ? `, like ${preview.sample.slice(0, 3).join(", ")}` : ""}.`}
              </p>
            </section>
          </div>

          <footer className="review-sheet-foot">
            <span className="muted tiny">Staged with your other changes in Organize.</span>
            <span className="organize-tray-actions">
              <Dialog.Close className="ghost">Cancel</Dialog.Close>
              <button
                type="button"
                className="primary"
                disabled={!canSave}
                onClick={() =>
                  onSave({
                    op: isNew ? "create" : "update",
                    kind: "cookbooks",
                    id: cookbook.id || `new-${Date.now()}`,
                    name: isNew ? name.trim() : cookbook.name,
                    to: {
                      name: name.trim(),
                      description,
                      rule,
                      public: isPublic,
                      position: cookbook.position || nextPosition,
                    },
                  })
                }
              >
                Stage
              </button>
            </span>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function RuleRow({ row, first, terms, onChange, onRemove }) {
  const [query, setQuery] = useState("");
  const chosen = row.values.map((id) => terms.find((t) => t.id === id) || { id, name: "Missing item", missing: true });
  const options = terms
    .filter((t) => !row.values.includes(t.id) && t.name.toLowerCase().includes(query.trim().toLowerCase()))
    .slice(0, 8);

  return (
    <div className="rule-row">
      <div className="rule-row-head">
        <span className="muted tiny">{first ? "Where" : "and"}</span>
        <select
          aria-label="Field"
          value={row.field}
          onChange={(e) => onChange({ field: e.target.value, values: [] })}
        >
          {RULE_FIELDS.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
        </select>
        <select aria-label="Condition" value={row.operator} onChange={(e) => onChange({ operator: e.target.value })}>
          {RULE_OPERATORS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        {onRemove ? (
          <button type="button" className="ghost small" aria-label="Remove condition" onClick={onRemove}><Icon name="x" /></button>
        ) : null}
      </div>
      <div className="rule-values">
        {chosen.map((term) => (
          <span key={term.id} className={`filter-chip${term.missing ? " missing" : ""}`}>
            {term.name}
            <button
              type="button"
              className="chip-remove"
              aria-label={`Remove ${term.name}`}
              onClick={() => onChange({ values: row.values.filter((v) => v !== term.id) })}
            >
              <Icon name="x" />
            </button>
          </span>
        ))}
        <input
          aria-label="Add a value"
          placeholder={`Search ${RULE_FIELDS.find((f) => f.key === row.field)?.plural}`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      {query.trim() ? (
        <div className="rule-options">
          {options.length ? (
            options.map((term) => (
              <button
                key={term.id}
                type="button"
                className="ghost small"
                onClick={() => {
                  onChange({ values: [...row.values, term.id] });
                  setQuery("");
                }}
              >
                {term.name} <span className="muted tiny">{term.count}</span>
              </button>
            ))
          ) : (
            <span className="muted tiny">No matches.</span>
          )}
        </div>
      ) : null}
    </div>
  );
}
