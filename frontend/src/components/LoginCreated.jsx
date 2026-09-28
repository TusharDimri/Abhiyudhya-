/* Shown in the side form right after a login is made (a new trainer,
   principal or user): the username and password to hand over, each with a
   copy button. The password is never shown again. */
import { useState } from "react";

function CopyField({ label, value }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // older browsers / no permission: copy through a hidden text box
      const box = document.createElement("textarea");
      box.value = value;
      document.body.appendChild(box);
      box.select();
      document.execCommand("copy");
      box.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="field">
      <label>{label}</label>
      <div className="copy-row">
        <input className="input copy-value" value={value} readOnly onFocus={(e) => e.target.select()} />
        <button type="button" className="btn btn-ghost btn-sm" onClick={copy} aria-label={`Copy ${label.toLowerCase()}`}>
          {copied ? "✓ Copied" : "📋 Copy"}
        </button>
      </div>
    </div>
  );
}

export default function LoginCreated({ name, username, password, onDone }) {
  return (
    <div className="overlay">
      <div className="drawer" role="dialog" aria-label="Login created">
        <header>
          <div>
            <h3 style={{ margin: 0 }}>Login created</h3>
            <span className="drawer-sub">{name ? `${name} can now log in with these details.` : "They can now log in with these details."}</span>
          </div>
        </header>
        <div className="body">
          <div className="prefill-note">✓ Saved. Copy the username and password and share them with {name || "them"}.</div>
          <CopyField label="Username" value={username} />
          <CopyField label="Password" value={password} />
          <p className="muted" style={{ fontSize: ".82rem" }}>
            This password is shown only now. They'll be asked to set their own password the first time they log in.
            If it's lost, reset it from Users &amp; Access.
          </p>
        </div>
        <footer>
          <button type="button" className="btn btn-primary" onClick={onDone}>Done</button>
        </footer>
      </div>
    </div>
  );
}
