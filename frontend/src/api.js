// AOI Tool - API helpers

const API_BASE = import.meta.env.VITE_API_URL || "";

export { API_BASE };

export async function fetchInspection(type, force = false) {
  const url = `${API_BASE}/api/inspect/${type}${force ? "?force=true" : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Server error");
  }
  return res.json();
}

export async function fetchStatus() {
  const res = await fetch(`${API_BASE}/api/status`);
  return res.json();
}

export async function fetchMode() {
  const res = await fetch(`${API_BASE}/api/mode`);
  return res.json();
}

export async function postMode(mode) {
  const res = await fetch(`${API_BASE}/api/mode/${mode}`, { method: "POST" });
  return res.json();
}

export async function postInspectText(text) {
  const res = await fetch(`${API_BASE}/api/inspect/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || res.statusText);
  }
  return res.json();
}

export async function postRefreshPpList() {
  const res = await fetch(`${API_BASE}/api/pp-list/refresh`, { method: "POST" });
  return res.json();
}

export async function fetchCliList() {
  const res = await fetch(`${API_BASE}/api/search/cli-list`);
  return res.json();
}

export async function fetchSearchPm(q, searchType, cli) {
  const params = new URLSearchParams({ q, search_type: searchType, cli });
  const res = await fetch(`${API_BASE}/api/search/pm?${params}`);
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || res.statusText);
  }
  return res.json();
}


/**
 * Stream AP refresh progress via SSE.
 * onMessage(msg) called for each progress line.
 * Returns a promise that resolves when __DONE__ is received.
 */
export function fetchApRefreshStream(onMessage) {
  return new Promise((resolve, reject) => {
    const es = new EventSource(`${API_BASE}/api/ap/refresh`);
    es.onmessage = (e) => {
      if (e.data === "__DONE__") {
        es.close();
        resolve();
      } else {
        onMessage(e.data);
      }
    };
    es.onerror = (err) => {
      es.close();
      reject(new Error("SSE connection error"));
    };
  });
}

export async function fetchApFromDb() {
  const res = await fetch(`${API_BASE}/api/ap`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Server error");
  }
  return res.json();
}

export async function fetchSyncStatus() {
  const res = await fetch(`${API_BASE}/api/sync/status`);
  return res.json();
}

export async function postSyncRun(syncType) {
  const res = await fetch(`${API_BASE}/api/sync/run?sync_type=${syncType}`, { method: "POST" });
  return res.json();
}


export function haranImageUrl(ppName) {
  return `${API_BASE}/api/image/${encodeURIComponent(ppName)}?type=hr`;
}

export function lpImageUrl(path) {
  return `${API_BASE}/api/lp-image/?path=${encodeURIComponent(path)}`;
}
