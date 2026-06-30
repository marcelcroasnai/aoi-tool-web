// AOI Tool - Users admin panel (requires users.manage)
import { useState, useEffect, useCallback } from "react";
import * as api from "../api.js";
import { useAuth } from "./AuthContext.jsx";

const ROLES = ["admin", "aoiteam", "visitor"];

function roleLabel(role, tr) {
  return role === "admin" ? tr.roleAdmin
    : role === "aoiteam" ? tr.roleAoiteam : tr.roleVisitor;
}

function Banner({ msg, t }) {
  if (!msg) return null;
  const c = msg.kind === "err" ? t.rowColors.red : t.rowColors.green;
  return (
    <div style={{
      background: c.bg, border: `1px solid ${c.border}55`, color: c.text,
      borderRadius: 8, padding: "8px 12px", fontSize: 13, marginBottom: 14,
    }}>{msg.kind === "err" ? "⚠ " : "✓ "}{msg.text}</div>
  );
}

function Card({ title, children, t, right }) {
  return (
    <div style={{
      background: t.bgTable, border: `1px solid ${t.border}`, borderRadius: 12,
      padding: 18, marginBottom: 18,
    }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 14 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: t.text,
                      fontFamily: "'IBM Plex Sans'" }}>{title}</div>
        <div style={{ flex: 1 }} />
        {right}
      </div>
      {children}
    </div>
  );
}

const inputStyle = (t) => ({
  padding: "8px 11px", borderRadius: 8, border: `1px solid ${t.borderInput}`,
  background: t.bgInput, color: t.text, fontSize: 13,
  fontFamily: "'IBM Plex Mono', monospace", outline: "none",
});
const btn = (t, kind = "neutral") => {
  const map = {
    primary: { bd: t.tabActive.color, bg: t.tabActive.bg, fg: t.tabActive.color },
    danger:  { bd: `${t.rowColors.red.border}55`, bg: "transparent", fg: t.rowColors.red.text },
    neutral: { bd: t.border, bg: "transparent", fg: t.textSub },
  }[kind];
  return {
    padding: "7px 12px", borderRadius: 8, cursor: "pointer",
    border: `1px solid ${map.bd}`, background: map.bg, color: map.fg,
    fontSize: 12, fontWeight: 700, fontFamily: "'IBM Plex Sans'",
  };
};

export function UsersPanel({ t, tr }) {
  const { user: me } = useAuth();

  const [users, setUsers]     = useState([]);
  const [registry, setReg]    = useState([]);
  const [roles, setRoles]     = useState({});      // working copy
  const [baseline, setBase]   = useState({});      // last-saved copy
  const [loading, setLoading] = useState(true);
  const [msg, setMsg]         = useState(null);

  // create-user form
  const [nu, setNu] = useState({ username: "", password: "", role: "aoiteam" });
  const [creating, setCreating] = useState(false);

  // inline password reset
  const [resetFor, setResetFor] = useState(null);
  const [resetPw, setResetPw]   = useState("");

  const flash = (kind, text) => { setMsg({ kind, text }); };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [u, p] = await Promise.all([api.listUsers(), api.fetchPermissions()]);
      setUsers(u.users);
      setReg(p.registry);
      setRoles(p.roles);
      setBase(JSON.parse(JSON.stringify(p.roles)));
    } catch (e) {
      flash("err", e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── user actions ──
  const createUser = async () => {
    if (!nu.username || !nu.password) return;
    setCreating(true); setMsg(null);
    try {
      await api.createUser(nu.username.trim(), nu.password, nu.role);
      setNu({ username: "", password: "", role: "aoiteam" });
      flash("ok", tr.usersCreated);
      await load();
    } catch (e) { flash("err", e.message); }
    finally { setCreating(false); }
  };

  const changeRole = async (username, role) => {
    setMsg(null);
    try { await api.updateUser(username, { role }); await load(); }
    catch (e) { flash("err", e.message); }
  };

  const submitReset = async (username) => {
    if (!resetPw) return;
    setMsg(null);
    try {
      await api.updateUser(username, { password: resetPw });
      setResetFor(null); setResetPw("");
      flash("ok", tr.usersPwReset);
    } catch (e) { flash("err", e.message); }
  };

  const removeUser = async (username) => {
    if (!window.confirm(tr.usersDeleteConfirm.replace("{name}", username))) return;
    setMsg(null);
    try { await api.deleteUser(username); flash("ok", tr.usersDeleted); await load(); }
    catch (e) { flash("err", e.message); }
  };

  // ── role permission editing ──
  const togglePerm = (role, perm) => {
    setRoles((prev) => {
      const cur = new Set(prev[role] || []);
      cur.has(perm) ? cur.delete(perm) : cur.add(perm);
      return { ...prev, [role]: registry.filter((p) => cur.has(p)) };
    });
  };

  const roleDirty = (role) =>
    JSON.stringify([...(roles[role] || [])].sort()) !==
    JSON.stringify([...(baseline[role] || [])].sort());

  const saveRole = async (role) => {
    setMsg(null);
    try {
      const res = await api.setRolePermissions(role, roles[role] || []);
      setRoles(res.roles);
      setBase(JSON.parse(JSON.stringify(res.roles)));
      flash("ok", `${roleLabel(role, tr)}: ${tr.usersSaved}`);
    } catch (e) { flash("err", e.message); }
  };

  if (loading) {
    return <div style={{ color: t.textMuted, padding: 24, fontFamily: "'IBM Plex Sans'" }}>…</div>;
  }

  return (
    <div style={{ fontFamily: "'IBM Plex Sans'" }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: t.text, marginBottom: 2 }}>{tr.usersTitle}</div>
      <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 18 }}>{tr.usersSubtitle}</div>

      <Banner msg={msg} t={t} />

      {/* ── Create user ── */}
      <Card title={tr.usersNew} t={t}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder={tr.authUser} value={nu.username}
            onChange={(e) => setNu({ ...nu, username: e.target.value })}
            style={{ ...inputStyle(t), flex: "1 1 160px" }} />
          <input placeholder={tr.authPassword} type="password" value={nu.password}
            onChange={(e) => setNu({ ...nu, password: e.target.value })}
            style={{ ...inputStyle(t), flex: "1 1 160px" }} />
          <select value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value })}
            style={{ ...inputStyle(t), flex: "0 0 auto" }}>
            {ROLES.map((r) => <option key={r} value={r}>{roleLabel(r, tr)}</option>)}
          </select>
          <button onClick={createUser} disabled={creating || !nu.username || !nu.password}
            style={{ ...btn(t, "primary"), opacity: creating || !nu.username || !nu.password ? 0.6 : 1 }}>
            {creating ? tr.authSaving : tr.usersCreate}
          </button>
        </div>
      </Card>

      {/* ── Accounts ── */}
      <Card title={`${tr.usersList} (${users.length})`} t={t}>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {users.map((u) => {
            const isSelf = u.username === me.username;
            return (
              <div key={u.username}>
                <div style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "9px 6px", borderBottom: `1px solid ${t.border}`,
                }}>
                  <div style={{ flex: "1 1 auto", minWidth: 0, fontSize: 14, fontWeight: 600,
                                color: t.text, fontFamily: "'IBM Plex Mono'" }}>
                    {u.username}{isSelf && (
                      <span style={{ fontSize: 11, color: t.textMuted, fontWeight: 400 }}> ({tr.usersYou})</span>
                    )}
                  </div>
                  {u.must_change_pw && (
                    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 8,
                                   background: t.rowColors.orange.bg, color: t.rowColors.orange.text,
                                   border: `1px solid ${t.rowColors.orange.border}55` }}>
                      {tr.usersMustChange}
                    </span>
                  )}
                  <select value={u.role} disabled={isSelf}
                    onChange={(e) => changeRole(u.username, e.target.value)}
                    style={{ ...inputStyle(t), padding: "5px 9px", opacity: isSelf ? 0.5 : 1 }}>
                    {ROLES.map((r) => <option key={r} value={r}>{roleLabel(r, tr)}</option>)}
                  </select>
                  <button onClick={() => { setResetFor(resetFor === u.username ? null : u.username); setResetPw(""); }}
                    style={btn(t, "neutral")}>{tr.usersResetPw}</button>
                  <button onClick={() => removeUser(u.username)} disabled={isSelf}
                    style={{ ...btn(t, "danger"), opacity: isSelf ? 0.4 : 1,
                             cursor: isSelf ? "not-allowed" : "pointer" }}>
                    {tr.usersDelete}
                  </button>
                </div>
                {resetFor === u.username && (
                  <div style={{ display: "flex", gap: 8, padding: "8px 6px 12px", alignItems: "center" }}>
                    <input placeholder={tr.authNewPw} type="password" value={resetPw} autoFocus
                      onChange={(e) => setResetPw(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && submitReset(u.username)}
                      style={{ ...inputStyle(t), flex: "1 1 200px" }} />
                    <button onClick={() => submitReset(u.username)} disabled={!resetPw}
                      style={{ ...btn(t, "primary"), opacity: resetPw ? 1 : 0.6 }}>{tr.authSave}</button>
                    <button onClick={() => { setResetFor(null); setResetPw(""); }}
                      style={btn(t, "neutral")}>✕</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* ── Role permissions ── */}
      <Card title={tr.usersRolePerms} t={t}>
        <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 14 }}>{tr.usersRolePermsHint}</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
          {ROLES.map((role) => {
            const isAdmin = role === "admin";
            const granted = new Set(isAdmin ? registry : (roles[role] || []));
            const dirty = !isAdmin && roleDirty(role);
            return (
              <div key={role} style={{
                border: `1px solid ${t.border}`, borderRadius: 10, padding: 14,
                background: t.expandBg,
              }}>
                <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>{roleLabel(role, tr)}</span>
                  <div style={{ flex: 1 }} />
                  {isAdmin
                    ? <span style={{ fontSize: 10, color: t.textMuted }}>{tr.usersAdminFixed}</span>
                    : <button onClick={() => saveRole(role)} disabled={!dirty}
                        style={{ ...btn(t, dirty ? "primary" : "neutral"),
                                 padding: "4px 10px", opacity: dirty ? 1 : 0.5,
                                 cursor: dirty ? "pointer" : "default" }}>
                        {dirty ? tr.authSave : tr.usersSaved}
                      </button>}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {registry.map((perm) => (
                    <label key={perm} style={{
                      display: "flex", alignItems: "center", gap: 8,
                      fontSize: 12, color: t.textSub,
                      cursor: isAdmin ? "default" : "pointer",
                      fontFamily: "'IBM Plex Mono'",
                    }}>
                      <input type="checkbox" checked={granted.has(perm)} disabled={isAdmin}
                        onChange={() => togglePerm(role, perm)} />
                      {perm}
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
