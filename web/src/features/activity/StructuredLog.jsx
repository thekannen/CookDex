import React from "react";

import Icon from "../../components/Icon";
import {
  buildDataMaintenanceView,
  buildPipelineExecutionSummary,
  buildStageResultSummary,
  groupLogEvents,
  parseLogEvents,
  renderGroupedLogEvents,
  renderSummaryTable,
  stageDisplayName,
} from "../../pages/tasks/taskLogUtils.jsx";

// A job's log as readable events (starts, results, warnings, summary tables),
// shared by the classic Tasks view and run details.
export default function StructuredLog({ text, isLive = false }) {
  const rawEvents = parseLogEvents(text);
  // Mark the last [start] as spinning if run is still active
  const events = isLive
    ? rawEvents.map((e, i) =>
        e.type === "start" && rawEvents.slice(i + 1).every(x => x.type !== "start")
          ? { ...e, type: "start-live" }
          : e
      )
    : rawEvents;
  const grouped = groupLogEvents(events);
  const dataMaintenanceView = buildDataMaintenanceView(events, Boolean(isLive));
  const stageStatusMeta = {
    succeeded: { label: "Completed", icon: "check-circle", cls: "log-stage-status-done" },
    failed: { label: "Failed", icon: "x-circle", cls: "log-stage-status-failed" },
    running: { label: "Running", icon: "loader", cls: "log-stage-status-running" },
    pending: { label: "Pending", icon: "info", cls: "log-stage-status-pending" },
    unknown: { label: "Unknown", icon: "alertTriangle", cls: "log-stage-status-unknown" },
  };
  return (
    <>
      {dataMaintenanceView ? (
        <>
          {renderGroupedLogEvents(groupLogEvents(dataMaintenanceView.prelude), {
            isLive: Boolean(isLive),
            keyPrefix: "dm-prelude",
          })}
          <div className="log-stage-list">
            {dataMaintenanceView.stages.map((stage, idx) => {
              const meta = stageStatusMeta[stage.status] || stageStatusMeta.unknown;
              const stageEvents = groupLogEvents(stage.events);
              const stageKey = `dm-stage-${stage.stage}-${idx}`;
              const stageIsLive = Boolean(isLive) && stage.status === "running";
              const summaryTitle = `${stageDisplayName(stage.stage)} Summary`;
              const stageResultSummary = buildStageResultSummary(stage, meta.label);
              const showStageResults = stage.started || stage.events.length > 0 || Boolean(stage.summary);
              return (
                <details
                  key={stageKey}
                  className={`log-stage-card ${meta.cls}`}
                  defaultOpen={stage.started || stage.status === "running" || stage.status === "failed"}
                >
                  <summary className="log-stage-summary">
                    <span className="log-stage-summary-left">
                      <Icon name={meta.icon} />
                      <span className="log-stage-name">{stageDisplayName(stage.stage)}</span>
                      <span className="log-stage-id">{stage.stage}</span>
                    </span>
                    <span className="log-stage-summary-right">
                      <span className="log-stage-state">{meta.label}</span>
                      {stage.elapsed && <span className="log-stage-elapsed">{stage.elapsed}</span>}
                      {stage.exitCode != null && <span className="log-stage-exit">exit {stage.exitCode}</span>}
                      <span className="log-stage-chevron">&#x25b6;</span>
                    </span>
                  </summary>
                  <div className="log-stage-body">
                    {stage.events.length === 0 && !stage.summary ? (
                      <div className="log-verbose">No stage output captured.</div>
                    ) : (
                      <>
                        {renderGroupedLogEvents(stageEvents, {
                          isLive: stageIsLive,
                          keyPrefix: `${stageKey}-events`,
                          expandProgressDetails: true,
                        })}
                        {stage.summary && renderSummaryTable(stage.summary, {
                          title: summaryTitle,
                          iconName: stage.status === "failed" ? "alertTriangle" : "check-circle",
                          keyPrefix: `${stageKey}-summary`,
                        })}
                      </>
                    )}
                    {showStageResults
                      ? renderSummaryTable(stageResultSummary, {
                          title: `${stageDisplayName(stage.stage)} Results`,
                          iconName: stage.status === "failed" ? "alertTriangle" : "check-circle",
                          keyPrefix: `${stageKey}-result`,
                        })
                      : null}
                  </div>
                </details>
              );
            })}
          </div>
          {renderGroupedLogEvents(groupLogEvents(dataMaintenanceView.trailer), {
            isLive: Boolean(isLive),
            keyPrefix: "dm-trailer",
          })}
          {renderSummaryTable(buildPipelineExecutionSummary(dataMaintenanceView.stages), {
            title: "Pipeline Results",
            iconName: "check-circle",
            keyPrefix: "dm-pipeline-summary",
          })}
        </>
      ) : (
        renderGroupedLogEvents(grouped, { isLive: Boolean(isLive), keyPrefix: "log" })
      )}
      {isLive && (
        <div className="log-live-tail">
          <span className="log-live-dot" /> live
        </div>
      )}
    </>
  );
}
