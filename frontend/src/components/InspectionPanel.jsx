// AOI Tool - Inspection Panel
import { useState, useCallback } from "react";
import { API_BASE, postRefreshPpList } from "../api.js";

export function InspectionPanel({ inspMode, setInspMode, loading, progressMsg, onRun, t, tr }) {
  const [textInput,      setTextInput]      = useState("");
  const [textInputError, setTextInputError] = useState(null);
  const [refreshing,     setRefreshing]     = useState(false);
  const [refreshMsg,     setRefreshMsg]     = useState(null);

  const handleRun = () => {
    if (inspMode === "text" && !textInput.trim()) {
      setTextInputError(tr.textInputEmpty);
      return;
    }
    setTextInputError(null);
    onRun(inspMode, textInput);
  };

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    setRefreshMsg(null);
    try {
      const d = await postRefreshPpList();
      setRefreshMsg({ ok: true, text: d.message });
    } catch (e) {
      setRefreshMsg({ ok: false, text: e.message });
    } finally {
      setRefreshing(false);
    }
  }, []);

  return (
    <div style={{
      display: "flex", gap: 16, alignItems: "flex-start",
      padding: "14px 18px", borderRadius: 12, marginBottom: 16,
      background: t.bgHeader, border: `1px solid ${t.border}`,
      flexWrap: "wrap",
    }}>
      {/* Mode selector */}
      <div>
        <div style={{ fontSize: 10, color: t.textMuted, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {tr.inspMode}
        </div>
        <div style={{ display: "flex", gap: 2, borderRadius: 8, overflow: "hidden", border: `1px solid ${t.border}` }}>
          {[["ap", tr.inspModeAp], ["vb", tr.inspModeVb], ["text", tr.inspModeText]].map(([mode, label]) => (
            <button
              key={mode}
              onClick={() => { setInspMode(mode); setTextInputError(null); }}
              style={{
                padding: "7px 16px", border: "none", cursor: "pointer",
                fontFamily: "'IBM Plex Sans'", fontSize: 12, fontWeight: 600,
                background: inspMode === mode ? t.tabActive.bg : "transparent",
                color:      inspMode === mode ? t.tabActive.color : t.textMuted,
                transition: "all 0.15s",
              }}
            >{label}</button>
          ))}
        </div>
      </div>

      {/* Text input */}
      {inspMode === "text" && (
        <div style={{ flex: "1 1 320px" }}>
          <div style={{ fontSize: 10, color: t.textMuted, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            {tr.textInputLabel}
          </div>
          <textarea
            value={textInput}
            onChange={e => { setTextInput(e.target.value); setTextInputError(null); }}
            placeholder={tr.textInputPlaceholder}
            rows={4}
            style={{
              width: "100%", padding: "8px 12px", borderRadius: 8,
              border: `1px solid ${textInputError ? "#ef4444" : t.borderInput}`,
              background: t.bgInput, color: t.text,
              fontFamily: "'IBM Plex Mono'", fontSize: 12,
              outline: "none", resize: "vertical", lineHeight: 1.6,
            }}
          />
          {textInputError && (
            <div style={{ fontSize: 11, color: "#ef4444", marginTop: 4 }}>⚠ {textInputError}</div>
          )}
        </div>
      )}

      {/* Run button */}
      <div style={{ alignSelf: "flex-end" }}>
        <button
          onClick={handleRun}
          disabled={loading}
          style={{
            padding: "8px 22px", borderRadius: 8, height: 38,
            border: `1px solid ${t.btnInspect.border}`,
            background: loading ? "transparent" : t.btnInspect.bg,
            color:      loading ? t.textMuted : t.btnInspect.color,
            fontFamily: "'IBM Plex Sans'", fontSize: 13, fontWeight: 600,
            cursor: loading ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", gap: 6,
          }}
        >
          {loading
            ? <><span style={{ display: "inline-block", animation: "spin 0.8s linear infinite" }}>⟳</span> {tr.btnRunning}</>
            : <>▶ {tr.btnInspect}</>
          }
        </button>
        {loading && progressMsg && inspMode === "ap" && (
          <div style={{
            marginTop: 6, fontSize: 11, color: t.textMuted,
            fontFamily: "'IBM Plex Mono'", maxWidth: 340,
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {progressMsg}
          </div>
        )}
      </div>

      {/* PP list refresh — AP mode only */}
      {inspMode === "ap" && (
        <div style={{ alignSelf: "flex-end" }}>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            title={tr.refreshPpList}
            style={{
              padding: "8px 14px", borderRadius: 8, height: 38,
              border: `1px solid ${t.border}`, background: "transparent",
              color: t.textMuted, fontFamily: "'IBM Plex Sans'", fontSize: 12,
              cursor: refreshing ? "not-allowed" : "pointer",
              display: "flex", alignItems: "center", gap: 6,
            }}
          >
            <span style={{ display: "inline-block", animation: refreshing ? "spin 0.8s linear infinite" : "none" }}>⟳</span>
            {!refreshing && tr.refreshPpList}
          </button>
          {refreshMsg && (
            <div style={{ fontSize: 10, marginTop: 3, color: refreshMsg.ok ? "#22c55e" : "#ef4444" }}>
              {refreshMsg.text}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
