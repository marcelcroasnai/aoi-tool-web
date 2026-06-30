// AOI Tool - Login screen + change-password form
import { useState } from "react";
import * as api from "../api.js";
import { useAuth } from "./AuthContext.jsx";

// Shared centered card shell
function AuthShell({ t, children }) {
  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: t.bg, color: t.text, padding: 24,
      fontFamily: "'IBM Plex Sans', sans-serif",
    }}>
      <div style={{
        width: 360, maxWidth: "100%",
        background: t.bgHeader, border: `1px solid ${t.border}`,
        borderRadius: 14, padding: 28,
        boxShadow: "0 12px 40px rgba(0,0,0,0.25)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 22 }}>
          <div style={{
            width: 38, height: 38, borderRadius: 10,
            background: "linear-gradient(135deg,#0ea5e9,#6366f1)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 19, fontWeight: 700, color: "#fff",
          }}>A</div>
          <div style={{ fontSize: 17, fontWeight: 700 }}>AOI Tool</div>
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({ label, type = "text", value, onChange, t, autoFocus }) {
  return (
    <label style={{ display: "block", marginBottom: 14 }}>
      <span style={{ display: "block", fontSize: 12, color: t.textMuted, marginBottom: 5, fontWeight: 600 }}>
        {label}
      </span>
      <input
        type={type} value={value} autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: "100%", padding: "9px 12px", borderRadius: 8,
          border: `1px solid ${t.borderInput}`, background: t.bgInput, color: t.text,
          fontSize: 14, fontFamily: "'IBM Plex Mono', monospace", outline: "none",
        }}
      />
    </label>
  );
}

function PrimaryButton({ children, disabled, t, onClick }) {
  return (
    <button type="submit" disabled={disabled} onClick={onClick} style={{
      width: "100%", padding: "10px 14px", borderRadius: 8, cursor: disabled ? "not-allowed" : "pointer",
      border: `1px solid ${t.tabActive.color}`, background: t.tabActive.bg, color: t.tabActive.color,
      fontSize: 14, fontWeight: 700, fontFamily: "'IBM Plex Sans'", opacity: disabled ? 0.6 : 1,
    }}>{children}</button>
  );
}

function ErrorLine({ msg, t }) {
  if (!msg) return null;
  const c = t.rowColors.red;
  return (
    <div style={{
      background: c.bg, border: `1px solid ${c.border}55`, color: c.text,
      borderRadius: 8, padding: "8px 12px", fontSize: 13, marginBottom: 14,
    }}>⚠ {msg}</div>
  );
}

// ─── Login ──────────────────────────────────────────────────────────────────────
export function Login({ t, tr }) {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (busy) return;
    setErr(null); setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (ex) {
      setErr(ex.message === "Login failed" ? tr.authBadCreds : (ex.message || tr.authBadCreds));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell t={t}>
      <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 2 }}>{tr.authTitle}</div>
      <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 18 }}>{tr.authSubtitle}</div>
      <form onSubmit={submit}>
        <ErrorLine msg={err} t={t} />
        <Field label={tr.authUser} value={username} onChange={setUsername} t={t} autoFocus />
        <Field label={tr.authPassword} type="password" value={password} onChange={setPassword} t={t} />
        <div style={{ marginTop: 6 }}>
          <PrimaryButton disabled={busy || !username || !password} t={t}>
            {busy ? tr.authLoggingIn : tr.authLogin}
          </PrimaryButton>
        </div>
      </form>
    </AuthShell>
  );
}

// ─── Change password (forced after first login, or voluntary) ─────────────────────
export function ChangePassword({ t, tr, forced = false, onDone, onCancel }) {
  const { refresh } = useAuth();
  const [cur, setCur]   = useState("");
  const [nw,  setNw]    = useState("");
  const [cnf, setCnf]   = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr]   = useState(null);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (busy) return;
    setErr(null);
    if (nw !== cnf) { setErr(tr.authPwMismatch); return; }
    setBusy(true);
    try {
      await api.changePassword(cur, nw);
      await refresh();
      onDone?.();
    } catch (ex) {
      setErr(ex.message || "Error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell t={t}>
      <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 2 }}>{tr.authChangeTitle}</div>
      {forced && (
        <div style={{ fontSize: 12, color: t.rowColors.orange.text, marginBottom: 16 }}>
          {tr.authChangeForced}
        </div>
      )}
      <form onSubmit={submit}>
        <ErrorLine msg={err} t={t} />
        <Field label={tr.authCurrentPw} type="password" value={cur} onChange={setCur} t={t} autoFocus />
        <Field label={tr.authNewPw}     type="password" value={nw}  onChange={setNw}  t={t} />
        <Field label={tr.authConfirmPw} type="password" value={cnf} onChange={setCnf} t={t} />
        <div style={{ marginTop: 6, display: "flex", gap: 8 }}>
          {!forced && onCancel && (
            <button type="button" onClick={onCancel} style={{
              flex: "0 0 auto", padding: "10px 14px", borderRadius: 8, cursor: "pointer",
              border: `1px solid ${t.border}`, background: "transparent", color: t.textMuted,
              fontSize: 14, fontWeight: 600,
            }}>✕</button>
          )}
          <div style={{ flex: 1 }}>
            <PrimaryButton disabled={busy || !cur || !nw || !cnf} t={t}>
              {busy ? tr.authSaving : tr.authSave}
            </PrimaryButton>
          </div>
        </div>
      </form>
    </AuthShell>
  );
}
