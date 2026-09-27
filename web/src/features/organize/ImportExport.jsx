import React, { useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { bundleFiles, exportFileName, summaryLines } from "./io.mjs";
import { describeChange, groupChanges } from "./model.mjs";

// Export the live taxonomy as JSON, or import a file as staged changes.
export default function ImportExport({ backend, onStage, onNotice, onError }) {
  const fileInput = useRef(null);
  const [busy, setBusy] = useState("");
  const [plan, setPlan] = useState(null);

  async function download() {
    setBusy("export");
    try {
      const document = await api("/organize/export", { timeout: 120000 });
      const blob = new Blob([`${JSON.stringify(document, null, 2)}\n`], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = Object.assign(window.document.createElement("a"), { href: url, download: exportFileName() });
      link.click();
      URL.revokeObjectURL(url);
      for (const warning of document.warnings || []) onNotice?.(warning, { tone: "warning" });
    } catch (exc) {
      onError?.(exc);
    } finally {
      setBusy("");
    }
  }

  async function importFiles(fileList) {
    const files = [...(fileList || [])];
    if (!files.length) return;
    setBusy("import");
    try {
      const parsed = [];
      const unreadable = [];
      for (const file of files) {
        try {
          parsed.push({ name: file.name, data: JSON.parse(await file.text()) });
        } catch {
          unreadable.push(`${file.name}: not valid JSON`);
        }
      }
      const { bundle, problems } = bundleFiles(parsed);
      const notes = [...unreadable, ...problems];
      if (!Object.keys(bundle).length) {
        setPlan({ changes: [], summary: {}, notes, empty: true });
        return;
      }
      const result = await api("/organize/import", { method: "POST", body: { document: bundle }, timeout: 120000 });
      setPlan({ ...result, notes });
    } catch (exc) {
      onError?.(exc);
    } finally {
      setBusy("");
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <div className="organize-io">
      <button type="button" className="ghost small" onClick={download} disabled={Boolean(busy)}>
        <Icon name="download" /> {busy === "export" ? "Exporting…" : "Export"}
      </button>
      <button type="button" className="ghost small" onClick={() => fileInput.current?.click()} disabled={Boolean(busy)}>
        <Icon name="upload" /> {busy === "import" ? "Reading…" : "Import"}
      </button>
      <input
        ref={fileInput}
        type="file"
        accept="application/json,.json"
        multiple
        hidden
        onChange={(e) => importFiles(e.target.files)}
      />
      {plan ? <ImportPreview plan={plan} backend={backend} onStage={onStage} onClose={() => setPlan(null)} /> : null}
    </div>
  );
}

function ImportPreview({ plan, backend, onStage, onClose }) {
  const changes = plan.changes || [];
  const lines = summaryLines(plan.summary);
  return (
    <Dialog.Root open onOpenChange={(value) => { if (!value) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="review-sheet" aria-describedby="import-desc">
          <header className="review-sheet-head">
            <div>
              <Dialog.Title className="review-sheet-title">
                {changes.length ? `Stage ${changes.length} change${changes.length === 1 ? "" : "s"} from this file?` : "Nothing to import"}
              </Dialog.Title>
              <Dialog.Description id="import-desc" className="muted">
                {changes.length
                  ? `Adds what's missing in ${backend} and fills gaps. Nothing is deleted, and nothing changes until you apply.`
                  : plan.empty
                    ? "Couldn't find anything to import in the files you picked."
                    : `Everything in this file is already in ${backend}.`}
              </Dialog.Description>
            </div>
            <Dialog.Close className="ghost small" aria-label="Close"><Icon name="x" /></Dialog.Close>
          </header>
          <div className="review-sheet-body">
            {lines.length ? (
              <ul className="import-summary">
                {lines.map((line) => <li key={line}>{line}</li>)}
              </ul>
            ) : null}
            {[...(plan.notes || []), ...(plan.skipped_sections || []).map((s) => `${s}: ${backend} doesn't support this, so it was left out`)].map(
              (note) => <p key={note} className="muted tiny"><Icon name="info" /> {note}</p>
            )}
            {groupChanges(changes).map(([title, group]) => (
              <section key={title} className="review-group">
                <h4>{title} <span className="review-count">{group.length}</span></h4>
                <ul className="review-list">
                  {group.map((change) => (
                    <li key={`${change.kind}-${change.id}`} className="review-row">
                      <Icon name={change.op === "create" ? "plus" : "pencil"} />
                      <span className="review-row-main"><strong>{describeChange(change)}</strong></span>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
          <footer className="review-sheet-foot">
            <span className="muted tiny">You'll review everything again before it's applied.</span>
            {changes.length ? (
              <button
                type="button"
                className="primary"
                onClick={() => {
                  for (const change of changes) onStage(change);
                  onClose();
                }}
              >
                Stage {changes.length} change{changes.length === 1 ? "" : "s"}
              </button>
            ) : (
              <Dialog.Close className="primary">Done</Dialog.Close>
            )}
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
