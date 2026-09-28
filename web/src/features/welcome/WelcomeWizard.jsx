import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { api, normalizeErrorMessage } from "../../utils.jsx";

export const WELCOME_DISMISSED_KEY = "cookdex_welcome_dismissed";

export function dismissWelcome() {
  try {
    window.localStorage.setItem(WELCOME_DISMISSED_KEY, "1");
  } catch {
    // Browser storage is a convenience; the wizard just shows again next time.
  }
}

export function welcomeDismissed() {
  try {
    return window.localStorage.getItem(WELCOME_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

// First run for a new owner: connect Mealie, then scan the library, ending
// on the owner's own findings instead of an empty dashboard.
export default function WelcomeWizard({ username, onConnected, onFinish, onError }) {
  const [step, setStep] = useState("connect");
  const [connection, setConnection] = useState(null);

  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <ol className="welcome-steps" aria-label="Setup steps">
        <li className="done"><Icon name="check-circle" /> Account</li>
        <li className={step === "connect" ? "current" : "done"} aria-current={step === "connect" ? "step" : undefined}>
          {step === "connect" ? <span className="step-dot">2</span> : <Icon name="check-circle" />} Connect Mealie
        </li>
        <li className={step === "scan" ? "current" : ""} aria-current={step === "scan" ? "step" : undefined}>
          <span className="step-dot">3</span> First scan
        </li>
      </ol>

      {step === "connect" ? (
        <ConnectStep
          onConnected={(result) => {
            setConnection(result);
            onConnected?.();
            setStep("scan");
          }}
          onError={onError}
        />
      ) : (
        <ScanStep connection={connection} username={username} onFinish={onFinish} onError={onError} />
      )}

      {step === "connect" ? (
        <button type="button" className="link-inline welcome-skip" onClick={() => onFinish()}>
          Skip setup for now
        </button>
      ) : null}
    </section>
  );
}

function ConnectStep({ onConnected, onError }) {
  const [address, setAddress] = useState("");
  const [token, setToken] = useState("");
  const [failure, setFailure] = useState("");

  const connect = useMutation({
    mutationFn: async () => {
      const test = await api("/settings/test/mealie", {
        method: "POST",
        body: { mealie_url: address, mealie_api_key: token },
        timeout: 20000,
      });
      if (!test?.ok) {
        throw new Error(test?.detail || "Couldn't reach Mealie with these details.");
      }
      await api("/settings", { method: "PUT", body: { env: { MEALIE_URL: address, MEALIE_API_KEY: token } } });
      return test;
    },
    onSuccess: (test) => {
      setFailure("");
      onConnected(test);
    },
    onError: (exc) => setFailure(normalizeErrorMessage(exc?.message || exc)),
  });

  function submit(event) {
    event.preventDefault();
    if (!address.trim() || !token.trim()) {
      setFailure("Enter both the Mealie address and an API token.");
      return;
    }
    connect.mutate();
  }

  return (
    <form className="welcome-card" onSubmit={submit} noValidate>
      <h2 id="welcome-title">Where is your Mealie?</h2>
      <p className="muted">CookDex works on your Mealie library through its API. Nothing in Mealie changes until you approve it.</p>

      <div className="welcome-field">
        <label htmlFor="welcome-mealie-address">Mealie address</label>
        <input
          id="welcome-mealie-address"
          type="text"
          inputMode="url"
          autoComplete="off"
          placeholder="http://mealie:9000"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
        />
        <p className="muted tiny">The address you open Mealie at. If both run in Docker on one network, use the service name, like http://mealie:9000. CookDex adds /api for you.</p>
      </div>

      <div className="welcome-field">
        <label htmlFor="welcome-mealie-token">API token</label>
        <input
          id="welcome-mealie-token"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <p className="muted tiny">In Mealie, open your profile, then API Tokens, and create one named CookDex. Mealie shows it only once.</p>
      </div>

      {failure ? (
        <p className="welcome-message error" role="alert"><Icon name="x-circle" /> {failure}</p>
      ) : null}

      <div className="welcome-actions">
        <button type="submit" className="primary" disabled={connect.isPending}>
          {connect.isPending ? "Checking…" : "Connect"}
        </button>
      </div>
    </form>
  );
}

function ScanStep({ connection, onFinish, onError }) {
  // The first scan is the Library's own scan, so the Library shows its
  // progress and findings, and the two never disagree.
  const start = useMutation({
    mutationFn: () => api("/library/scan", { method: "POST" }),
    onSuccess: () => onFinish?.(),
    onError: (exc) => onError?.(exc),
  });

  return (
    <div className="welcome-card">
      {connection?.detail ? (
        <p className="welcome-message success" role="status"><Icon name="check-circle" /> {connection.detail}</p>
      ) : null}
      <h2 id="welcome-title">Scan your library</h2>
      <p className="muted">
        CookDex checks every recipe for missing details, pages that aren't recipes, duplicates and messy names. It only
        looks: nothing in Mealie changes. You'll see it working on the Library page, and what it finds there.
      </p>
      <div className="welcome-actions">
        <button type="button" className="ghost" onClick={() => onFinish?.()}>
          Not now
        </button>
        <button type="button" className="primary" onClick={() => start.mutate()} disabled={start.isPending}>
          {start.isPending ? "Starting…" : "Scan my library"}
        </button>
      </div>
    </div>
  );
}
