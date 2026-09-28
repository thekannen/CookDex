import React, { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "../../utils.jsx";
import RunSheet from "../activity/RunSheet";
import JobSheet from "./JobSheet";
import { runOptions } from "./catalog.mjs";

// Opening a job, running it, scheduling it and following its run: shared by
// Tools and by pages that start a job in place (the Library's findings).
export function useJobRunner({ tasks, isOwner, taskTitle, onConfirm, onNotice, onError }) {
  const queryClient = useQueryClient();
  const [job, setJob] = useState(null); // { task, options }
  const [openRun, setOpenRun] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(task, options, { confirmed = false } = {}) {
    setBusy(true);
    try {
      const created = await api("/runs", { method: "POST", body: { task_id: task.task_id, options, confirmed } });
      setJob(null);
      setOpenRun(created.run_id);
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    } catch (exc) {
      onError(exc);
    } finally {
      setBusy(false);
    }
  }

  async function schedule(task, body) {
    const send = (allow) => api("/automations", { method: "POST", body: { ...body, allow_changes: allow } });
    const done = () => {
      setJob(null);
      queryClient.invalidateQueries({ queryKey: ["automations"] });
      onNotice(`“${body.name}” will run automatically. Find it under Automations.`);
    };
    setBusy(true);
    try {
      await send(false);
      done();
    } catch (exc) {
      if (String(exc?.message || "") === "approval_required") {
        onConfirm({
          message: `Let “${body.name}” change Mealie on its own each time it runs? A backup is made first. You can pause or change it under Automations.`,
          confirmLabel: "Allow and save",
          danger: false,
          action: async () => {
            try {
              await send(true);
              done();
            } catch (err) {
              onError(err);
            }
          },
        });
      } else {
        onError(exc);
      }
    } finally {
      setBusy(false);
    }
  }

  // From a finished preview: the same job, for real.
  function applyForReal(previewRun) {
    const task = tasks.find((t) => t.task_id === previewRun.task_id);
    if (!task) return;
    const options = runOptions(task, previewRun.options, { apply: true });
    const go = () => run(task, options, { confirmed: isOwner });
    onConfirm({
      message: `Apply “${taskTitle(task.task_id)}” to Mealie now? It makes the same changes the preview found${options.backup_first ? ", after a backup" : ""}.`,
      confirmLabel: "Apply changes",
      danger: false,
      action: go,
    });
  }

  const canApplyTask = (taskId) => isOwner || Boolean(tasks.find((t) => t.task_id === taskId)?.policy?.allow_dangerous);


  function openJob(taskId, options = {}) {
    const task = tasks.find((t) => t.task_id === taskId);
    if (task) setJob({ task, options: options || {} });
  }

  const sheets = (
    <>
      {job ? (
        <JobSheet
          key={job.task.task_id}
          task={job.task}
          initialOptions={job.options}
          open
          onOpenChange={(open) => { if (!open) setJob(null); }}
          isOwner={isOwner}
          busy={busy}
          onRun={run}
          onSchedule={schedule}
        />
      ) : null}
      <RunSheet
        runId={typeof openRun === "string" ? openRun : null}
        open={Boolean(openRun)}
        onOpenChange={(open) => { if (!open) setOpenRun(null); }}
        taskTitle={taskTitle}
        canApply={canApplyTask}
        onApplyForReal={applyForReal}
        onError={onError}
      />
    </>
  );

  return { openJob, setJob, setOpenRun, sheets };
}
