import React from "react";

import Icon from "./Icon";

// What a page shows when it couldn't load: the reason and a way to try again,
// never an empty state that looks like there's nothing there.
export default function LoadError({ what, error, onRetry, retrying }) {
  const reason = String(error?.message || error || "").trim();
  return (
    <div className="load-error" role="alert">
      <Icon name="x-circle" />
      <div>
        <strong>Couldn't load {what}.</strong>
        {reason ? <p className="muted">{reason}</p> : null}
      </div>
      {onRetry ? (
        <button type="button" className="ghost small" onClick={onRetry} disabled={retrying}>
          {retrying ? "Trying…" : "Try again"}
        </button>
      ) : null}
    </div>
  );
}
