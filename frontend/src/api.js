// AOI Tool - API helpers (with auth)

const API_BASE = import.meta.env.VITE_API_URL || "";
const TOKEN_KEY = "aoi_token";

export { API_BASE };

// ─── Token storage ─────────────────────────────────────────────────────────────
export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else       localStorage.removeItem(TOKEN_KEY);
  } catch { /* ignore */ }
}

// Called when any request comes back 401 (expired/invalid token).
let _onAuthError = () => {};
export function setOnAuthError(fn) { _onAuthError = fn || (() => {}); }

function authHeaders(extra = {}) {
  const t = getToken();
  return t ? { ...extra, Authorization: `Bearer ${t}` } : { ...extra };
}

// Central fetch: injects the bearer token and trips logout on 401.
async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: authHeaders(opts.headers || {}),
  });
  if (res.status === 401) {
    setToken(null);
    _onAuthError();
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || "Unauthorized");
  }
  return res;
}

async function jsonOrThrow(res) {
  if (!res.ok) {
    const e = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(e.detail || "Server error");
  }
  return res.json();
}

// ─── Auth API ───────────────────────────────────────────────────────────────────
export async function login(username, password) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || "Login failed");
  }
  return res.json();               // { token, user }
}

export async function me() {
  return jsonOrThrow(await apiFetch("/api/auth/me"));
}

export async function changePassword(oldPassword, newPassword) {
  const res = await apiFetch("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
  return jsonOrThrow(res);
}

// ─── User management (admin) ─────────────────────────────────────────────────────
export async function listUsers() {
  return jsonOrThrow(await apiFetch("/api/auth/users"));
}
export async function createUser(username, password, role) {
  return jsonOrThrow(await apiFetch("/api/auth/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, role }),
  }));
}
export async function updateUser(username, patch) {
  return jsonOrThrow(await apiFetch(`/api/auth/users/${encodeURIComponent(username)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }));
}
export async function deleteUser(username) {
  return jsonOrThrow(await apiFetch(`/api/auth/users/${encodeURIComponent(username)}`, {
    method: "DELETE",
  }));
}
export async function fetchPermissions() {
  return jsonOrThrow(await apiFetch("/api/auth/permissions"));
}
export async function setRolePermissions(role, permissions) {
  return jsonOrThrow(await apiFetch(`/api/auth/roles/${encodeURIComponent(role)}/permissions`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ permissions }),
  }));
}

// ─── Inspection / data ────────────────────────────────────────────────────────
export async function fetchInspection(type, force = false) {
  const path = `/api/inspect/${type}${force ? "?force=true" : ""}`;
  return jsonOrThrow(await apiFetch(path));
}

export async function fetchStatus() {
  return jsonOrThrow(await apiFetch("/api/status"));
}

export async function fetchMode() {
  return jsonOrThrow(await apiFetch("/api/mode"));
}

export async function postMode(mode) {
  return jsonOrThrow(await apiFetch(`/api/mode/${mode}`, { method: "POST" }));
}

export async function postInspectText(text) {
  return jsonOrThrow(await apiFetch("/api/inspect/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  }));
}

export async function postRefreshPpList() {
  return jsonOrThrow(await apiFetch("/api/pp-list/refresh", { method: "POST" }));
}

export async function fetchCliList() {
  return jsonOrThrow(await apiFetch("/api/search/cli-list"));
}

export async function fetchSearchPm(q, searchType, cli) {
  const params = new URLSearchParams({ q, search_type: searchType, cli });
  return jsonOrThrow(await apiFetch(`/api/search/pm?${params}`));
}

/**
 * Stream AP refresh progress via SSE.
 * EventSource can't send headers, so the token rides as a query param
 * (the backend accepts it there for this endpoint only).
 */
export function fetchApRefreshStream(onMessage) {
  return new Promise((resolve, reject) => {
    const t = getToken();
    const url = `${API_BASE}/api/ap/refresh${t ? `?token=${encodeURIComponent(t)}` : ""}`;
    const es = new EventSource(url);
    es.onmessage = (e) => {
      if (e.data === "__DONE__") { es.close(); resolve(); }
      else onMessage(e.data);
    };
    es.onerror = () => { es.close(); reject(new Error("SSE connection error")); };
  });
}

export async function fetchApFromDb() {
  return jsonOrThrow(await apiFetch("/api/ap"));
}

export async function fetchSyncStatus() {
  return jsonOrThrow(await apiFetch("/api/sync/status"));
}

export async function postSyncRun(syncType) {
  return jsonOrThrow(await apiFetch(`/api/sync/run?sync_type=${syncType}`, { method: "POST" }));
}

// ─── Image URLs (these load via <img>, so they stay token-free / open) ──────────
export function haranImageUrl(ppName) {
  return `${API_BASE}/api/image/${encodeURIComponent(ppName)}?type=hr`;
}
export function lpImageUrl(path) {
  return `${API_BASE}/api/lp-image/?path=${encodeURIComponent(path)}`;
}
