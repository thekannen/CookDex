import React, { useState } from "react";
import { formatDistanceToNow } from "date-fns";

import Icon from "../../components/Icon";
import { api } from "../../utils.jsx";
import { ROLES, generatePassword, signInAddress, suggestUsername } from "./people.mjs";

// Who can sign in, what they can do, and how to get someone started: add
// them, then send the sign-in details CookDex shows you.
export default function UsersPage({ users, session, onNotice, onError, onConfirm, refreshUsers }) {
  const [adding, setAdding] = useState(false);
  const [handoff, setHandoff] = useState(null); // { username, password, fresh }
  const me = users.find((item) => item.username === session?.username);
  const others = users.filter((item) => item.username !== session?.username);

  async function resetPassword(person) {
    const password = generatePassword();
    try {
      await api(`/users/${encodeURIComponent(person.username)}/reset-password`, {
        method: "POST",
        body: { password, force_reset: true },
      });
      await refreshUsers();
      setHandoff({ username: person.username, password, fresh: false });
    } catch (exc) {
      onError(exc);
    }
  }

  function changeRole(person, role) {
    const run = async () => {
      try {
        await api(`/users/${encodeURIComponent(person.username)}/role`, { method: "PATCH", body: { role } });
        await refreshUsers();
        onNotice(`${person.username} is now ${ROLES[role].article} ${ROLES[role].label.toLowerCase()}.`);
      } catch (exc) {
        onError(exc);
      }
    };
    onConfirm({
      message:
        role === "owner"
          ? `Make ${person.username} an owner? Owners can change settings, manage people, and approve automations that change Mealie.`
          : `Make ${person.username} an editor? They keep using CookDex but can't change settings or people.`,
      confirmLabel: role === "owner" ? "Make owner" : "Make editor",
      danger: false,
      action: run,
    });
  }

  function remove(person) {
    onConfirm({
      message: `Remove ${person.username}? They're signed out and can't sign in again. What they did in CookDex stays.`,
      confirmLabel: "Remove",
      action: async () => {
        try {
          await api(`/users/${encodeURIComponent(person.username)}`, { method: "DELETE" });
          await refreshUsers();
          onNotice(`Removed ${person.username}.`);
        } catch (exc) {
          onError(exc);
        }
      },
    });
  }

  return (
    <section className="people">
      <div className="people-main">
        <header className="people-head">
          {!adding ? (
            <button type="button" className="primary small" onClick={() => { setAdding(true); setHandoff(null); }}>
              <Icon name="plus" /> Add a person
            </button>
          ) : null}
        </header>

        {handoff ? <Handoff {...handoff} onDone={() => setHandoff(null)} /> : null}

        {adding ? (
          <AddPerson
            onCancel={() => setAdding(false)}
            onAdded={async (person) => {
              setAdding(false);
              await refreshUsers();
              setHandoff({ ...person, fresh: true });
            }}
            onError={onError}
          />
        ) : null}

        <ul className="people-list">
          {me ? <PersonRow person={me} isMe /> : null}
          {others.map((person) => (
            <PersonRow
              key={person.username}
              person={person}
              onReset={() => resetPassword(person)}
              onRole={(role) => changeRole(person, role)}
              onRemove={() => remove(person)}
            />
          ))}
        </ul>
        {others.length === 0 && !adding ? (
          <p className="muted tiny">Just you so far. Add someone who helps look after the recipes, or a kitchen tablet.</p>
        ) : null}

        {me ? <MyPassword username={me.username} onNotice={onNotice} onError={onError} /> : null}
      </div>

      <aside className="people-side">
        <article className="card">
          <h3><Icon name="users" /> What each role can do</h3>
          {Object.entries(ROLES).map(([key, role]) => (
            <div key={key} className="role-explainer">
              <strong>{role.label}</strong>
              <ul>
                {role.can.map((line) => <li key={line}>{line}</li>)}
              </ul>
            </div>
          ))}
        </article>
      </aside>
    </section>
  );
}

function PersonRow({ person, isMe, onReset, onRole, onRemove }) {
  const role = ROLES[person.role] || ROLES.editor;
  const last = person.last_sign_in ? `Last signed in ${formatDistanceToNow(new Date(person.last_sign_in), { addSuffix: true })}` : "Hasn't signed in yet";
  return (
    <li className="person">
      <span className="person-avatar" aria-hidden="true">{person.username.slice(0, 1).toUpperCase()}</span>
      <div className="person-main">
        <div className="person-name">
          <strong>{person.username}</strong>
          <span className={`status-pill ${person.role === "owner" ? "success" : "neutral"}`}>{role.label}</span>
          {isMe ? <span className="status-pill neutral">You</span> : null}
        </div>
        <span className="muted tiny">
          {last}
          {person.force_password_reset ? " · picks a new password at next sign-in" : ""}
        </span>
      </div>
      {!isMe ? (
        <div className="person-actions">
          <button type="button" className="ghost small" onClick={onReset}>
            <Icon name="key" /> New password
          </button>
          <button type="button" className="ghost small" onClick={() => onRole(person.role === "owner" ? "editor" : "owner")}>
            {person.role === "owner" ? "Make editor" : "Make owner"}
          </button>
          <button type="button" className="ghost icon-btn" aria-label={`Remove ${person.username}`} onClick={onRemove}>
            <Icon name="trash" />
          </button>
        </div>
      ) : null}
    </li>
  );
}

function AddPerson({ onCancel, onAdded, onError }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("editor");
  const [busy, setBusy] = useState(false);
  const username = suggestUsername(name);

  async function submit(event) {
    event.preventDefault();
    const password = generatePassword();
    setBusy(true);
    try {
      await api("/users", { method: "POST", body: { username, password, force_reset: true, role } });
      onAdded({ username, password });
    } catch (exc) {
      onError(exc);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card add-person" onSubmit={submit}>
      <h4>Add a person</h4>
      <label className="field">
        <span>Their sign-in name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="like sam, or kitchen-tablet" autoFocus />
        {name && username !== name ? <span className="muted tiny">They'll sign in as <strong>{username}</strong>.</span> : null}
      </label>
      <div className="builder-modes" role="radiogroup" aria-label="Role">
        {Object.entries(ROLES).map(([key, item]) => (
          <label key={key} className={role === key ? "is-picked" : ""}>
            <input type="radio" name="new-role" checked={role === key} onChange={() => setRole(key)} />
            <span><strong>{item.label}</strong><span className="muted tiny">{item.short}</span></span>
          </label>
        ))}
      </div>
      <p className="muted tiny">CookDex makes a temporary password for them. They choose their own the first time they sign in.</p>
      <div className="add-person-actions">
        <button type="button" className="ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" className="primary" disabled={busy || username.length < 3}>
          <Icon name="plus" /> Add {username || "person"}
        </button>
      </div>
    </form>
  );
}

function Handoff({ username, password, fresh, onDone }) {
  const [copied, setCopied] = useState(false);
  const address = signInAddress();
  const text = `Sign in to CookDex\n${address}\nName: ${username}\nTemporary password: ${password}\nYou'll choose your own password when you sign in.`;
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      // Clipboard can be blocked; the details are on screen to copy by hand.
    }
  }
  return (
    <section className="card handoff" aria-live="polite">
      <h4><Icon name="check-circle" /> {fresh ? `${username} can sign in now` : `New password for ${username}`}</h4>
      <p className="muted">Send them these details. This is the only time the password is shown.</p>
      <dl className="handoff-details">
        <div><dt>Address</dt><dd><code>{address}</code></dd></div>
        <div><dt>Name</dt><dd><code>{username}</code></dd></div>
        <div><dt>Temporary password</dt><dd><code>{password}</code></dd></div>
      </dl>
      <div className="add-person-actions">
        <button type="button" className="ghost" onClick={onDone}>Done</button>
        <button type="button" className="primary" onClick={copy}>
          <Icon name="copy" /> {copied ? "Copied" : "Copy all"}
        </button>
      </div>
    </section>
  );
}

function MyPassword({ username, onNotice, onError }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [show, setShow] = useState(false);
  const mismatch = again && password !== again;

  async function submit(event) {
    event.preventDefault();
    try {
      await api(`/users/${encodeURIComponent(username)}/reset-password`, { method: "POST", body: { password, force_reset: false } });
      setOpen(false);
      setPassword("");
      setAgain("");
      onNotice("Your password is changed. Other devices you were signed in on are signed out.");
    } catch (exc) {
      onError(exc);
    }
  }

  if (!open) {
    return (
      <button type="button" className="ghost small my-password-open" onClick={() => setOpen(true)}>
        <Icon name="lock" /> Change my password
      </button>
    );
  }
  return (
    <form className="card add-person" onSubmit={submit}>
      <h4>Change my password</h4>
      <label className="field">
        <span>New password</span>
        <input type={show ? "text" : "password"} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <span className="muted tiny">At least 8 characters, with a capital letter, a small letter and a number.</span>
      </label>
      <label className="field">
        <span>Same again</span>
        <input type={show ? "text" : "password"} autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
        {mismatch ? <span className="tiny danger-text">These don't match yet.</span> : null}
      </label>
      <label className="field checkbox-field">
        <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
        <span>Show passwords</span>
      </label>
      <div className="add-person-actions">
        <button type="button" className="ghost" onClick={() => setOpen(false)}>Cancel</button>
        <button type="submit" className="primary" disabled={!password || password !== again}>Change password</button>
      </div>
    </form>
  );
}
