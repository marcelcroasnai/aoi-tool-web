// AOI Tool - SyncBar
// Bottom bar showing last sync times and manual sync trigger buttons.

import { useState, useEffect, useCallback } from "react";
import { fetchSyncStatus, postSyncRun } from "../api.js";

const POLL_INTERVAL_IDLE    = 30000;  // 30s when idle
const POLL_INTERVAL_RUNNING = 2000;   // 2s when a sync is running

function _fmtTime(isoStr) {
  if (!isoStr) return null;
  try {
    const d = new Date(isoStr + "Z");
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch { return isoStr; }
}

function _isRunning(status, type) {
  return (status?.running || []).some(r => r.sync_type === type);
}

function _anyRunning(status) {
  return (status?.running || []).length > 0;
}

function SyncPill({ label, info, running, t }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6,
      padding: "3px 10px", borderRadius: 12,
      background: t.bgInput, border: `1px solid ${t.border}`,
      fontSize: 11,
    }}>
      {running && (
        <span style={{
          display: "inline-block", width: 10, height: 10,
          border: `2px solid ${t.border}`, borderTopColor: "#38bdf8",
          borderRadius: "50%", animation: "spin 0.8s linear infinite",
        }} />
      )}
      <span style={{ color: t.textMuted, fontWeight: 600 }}>{label}:</span>
      <span style={{ color: running ? "#38bdf8" : t.text, fontFamily: "monospace" }}>
        {running ? "…" : (info || "—")}
      </span>
    </div>
  );
}

export function SyncBar({ t, tr }) {
  const [status,   setStatus]   = useState(null);
  const [loading,  setLoading]  = useState({ full: false, ap: false });

  const fetchStatus = useCallback(() => {
    fetchSyncStatus()
      .then(setStatus)
      .catch(() => {});
  }, []);

  // Poll sync status — faster when running
  useEffect(() => {
    fetchStatus();
    const interval = _anyRunning(status) ? POLL_INTERVAL_RUNNING : POLL_INTERVAL_IDLE;
    const id = setInterval(fetchStatus, interval);
    return () => clearInterval(id);
  }, [status?.running?.length]);

  const runSync = useCallback(async (type) => {
    setLoading(l => ({ ...l, [type === "full" ? "full" : "ap"]: true }));
    try {
      await postSyncRun(type);
      // Start fast polling immediately
      fetchStatus();
    } catch (e) {
      console.error("Sync error:", e);
    } finally {
      setLoading(l => ({ ...l, [type === "full" ? "full" : "ap"]: false }));
    }
  }, [fetchStatus]);




  const anyRunning    = _anyRunning(status);
  const ppRunning     = _isRunning(status, "pp") || _isRunning(status, "cli") || _isRunning(status, "pm_type");
  const apRunning     = _isRunning(status, "ap");

  const lastAp  = _fmtTime(status?.ap?.finished_at);

  const btnStyle = (active, color = "#0ea5e9") => ({
    display: "flex", alignItems: "center", gap: 5,
    padding: "4px 12px", borderRadius: 8,
    background: active ? `${color}20` : t.bgInput,
    color: active ? color : t.textMuted,
    border: `1px solid ${active ? color + "60" : t.border}`,
    fontFamily: "'IBM Plex Sans'", fontSize: 11, fontWeight: 600,
    cursor: active ? "pointer" : "not-allowed",
    opacity: active ? 1 : 0.6,
    transition: "all 0.15s",
  });

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
    }}>
      {/* AP sync pill */}
      <SyncPill label={tr.syncLastAp} info={lastAp} running={apRunning} t={t} />

      {/* Divider */}
      <div style={{ width: 1, height: 20, background: t.border }} />

      {/* PP + CLI sync button */}
      <button
        onClick={() => !anyRunning && runSync("full")}
        disabled={anyRunning || loading.full}
        style={btnStyle(!anyRunning && !loading.full, "#6366f1")}
      >
        {ppRunning
          ? <><span style={{ animation: "spin 0.8s linear infinite", display: "inline-block" }}>⟳</span> {tr.syncRunning}</>
          : <>⟳ {tr.syncBtnFull}</>
        }
      </button>

      {/* AP refresh button */}
      <button
        onClick={() => !anyRunning && runSync("ap")}
        disabled={anyRunning || loading.ap}
        style={btnStyle(!anyRunning && !loading.ap, "#0ea5e9")}
      >
        {apRunning
          ? <><span style={{ animation: "spin 0.8s linear infinite", display: "inline-block" }}>⟳</span> {tr.syncRunning}</>
          : <>↻ {tr.syncBtnAp}</>
        }
      </button>
    </div>
  );
}
