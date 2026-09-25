import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { apiError } from "../lib/api";

const DEMO = [
  ["Super Admin", "sa@rnaf.demo"],
  ["Org Admin", "oa@rnaf.demo"],
  ["District Mgr", "dm@rnaf.demo"],
  ["Principal", "pr@rnaf.demo"],
  ["Trainer", "vt@rnaf.demo"],
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      await login(email.trim(), password);
      nav("/app/dashboard");
    } catch (e2) {
      setErr(apiError(e2));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <div className="auth-logo">Abhiyudhya</div>
        <h2 style={{ textAlign: "center", marginBottom: 2 }}>Welcome back</h2>
        <p className="muted" style={{ textAlign: "center", marginTop: 0, fontSize: ".85rem" }}>
          Vocational Education Management
        </p>
        <form onSubmit={submit} style={{ marginTop: "1.2rem" }}>
          <div className="field">
            <label>Email</label>
            <input className="input" type="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@org.demo" />
          </div>
          <div className="field">
            <label>Password</label>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          {err && <div className="field-error" style={{ marginBottom: ".6rem" }}>{err}</div>}
          <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        {import.meta.env.DEV && (
        <div className="demo-note">
          <b>Demo logins</b> (password: <code>Password@123</code>)
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
            {DEMO.map(([label, e]) => (
              <button key={e} type="button" className="btn btn-ghost btn-sm"
                onClick={() => { setEmail(e); setPassword("Password@123"); }}>
                {label}
              </button>
            ))}
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
