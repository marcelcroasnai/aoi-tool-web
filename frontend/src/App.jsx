import { useState, useEffect, useCallback } from "react";

import { TR }         from "./constants/translations.js";
import { THEMES }     from "./constants/themes.js";
import {
  API_BASE,
  fetchApFromDb,
  fetchApRefreshStream,
  fetchInspection,
  fetchSyncStatus,
  fetchMode,
  postMode,
  postSyncRun,
  postInspectText,
} from "./api.js";

import { LangToggle } from "./components/shared.jsx";
import { ImageViewer }           from "./components/ImageViewer.jsx";
import { InspectionPanel }       from "./components/InspectionPanel.jsx";
import { InspectionTable }       from "./components/InspectionTable.jsx";
import { SearchPmTab }           from "./components/SearchPmTab.jsx";
import { IdeasPanel }            from "./components/IdeasPanel.jsx";
import { SyncBar }               from "./components/SyncBar.jsx";


export default function App() {
  const [isDark,       setIsDark]       = useState(false);
  const [lang,         setLang]         = useState("de");
  const [appMode,      setAppMode]      = useState("live");
  const [modeLoading,  setModeLoading]  = useState(false);
  const [tab,          setTab]          = useState("inspection");
  const [inspMode,     setInspMode]     = useState("ap");

  const [apData,       setApData]       = useState(null);
  const [vbData,       setVbData]       = useState(null);
  const [textData,     setTextData]     = useState(null);
  const [loading,      setLoading]      = useState(false);
  const [progressMsg,  setProgressMsg]  = useState(null);
  const [error,        setError]        = useState(null);
  const [lastTime,     setLastTime]     = useState(null);
  const [duration,     setDuration]     = useState(null);

  const [viewer,       setViewer]       = useState(null); // { mode, images }

  const t  = THEMES[isDark ? "dark" : "light"];
  const tr = TR[lang];

  const [ideasOpen, setIdeasOpen] = useState(false);

  // ── Init ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchMode()
      .then(d => setAppMode(d.mode))
      .catch(() => {});
  }, []);

  // ── Mode switch ───────────────────────────────────────────────────────────
  const switchMode = useCallback(async (newMode) => {
    if (newMode === appMode) return;
    setModeLoading(true);
    try {
      await postMode(newMode);
      setAppMode(newMode);
      setApData(null); setVbData(null); setTextData(null);
      setError(null);
    } catch (e) {
      console.error(e);
    } finally {
      setModeLoading(false);
    }
  }, [appMode]);

  // ── Run inspection ────────────────────────────────────────────────────────
  const runInspection = useCallback(async (mode, textInput) => {
    setLoading(true);
    setError(null);

    try {
      let data;
      if (mode === "ap") {
        if (appMode === "test") {
          // Test mode: use old pipeline (reads from TEST_AP_HTML_FILE)
          data = await fetchInspection("ap", true);
          setApData(data.results);
        } else {
          // Live mode: SSE stream with mtime check + DB
          try {
            await fetchApRefreshStream((msg) => setProgressMsg(msg));
          } catch (e) {
            // SSE failed — continue to fetch anyway
          }
          setProgressMsg(null);
          data = await fetchApFromDb();
          setApData(data.results);
        }
      } else if (mode === "vb") {
        data = await fetchInspection("vb", true);
        setVbData(data.results);
      } else {
        data = await postInspectText(textInput);
        setTextData(data.results);
      }
      setLastTime(data.timestamp);
      setDuration(data.duration_seconds);
    } catch (e) {
      setError(e.message);
    } finally {
      setProgressMsg(null);
      setLoading(false);
    }
  }, [appMode]);

  const currentData = inspMode === "ap" ? apData : inspMode === "vb" ? vbData : textData;

  const openViewer  = useCallback((mode, images) => setViewer({ mode, images }), []);
  const closeViewer = useCallback(() => setViewer(null), []);

  return (
    <div style={{
      minHeight: "100vh", background: t.bg, color: t.text,
      fontFamily: "'IBM Plex Mono','Consolas',monospace",
      transition: "background 0.3s, color 0.3s",
      zoom: 1.15,   // global scale-up — fonts read too small on FullHD at 100%
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        @keyframes spin { to { transform: rotate(360deg); } }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${t.scrollbar}; border-radius: 3px; }
        button { transition: all 0.15s; }
      `}</style>

      {/* Image viewer overlay */}
      {viewer && (
        <ImageViewer
          mode={viewer.mode}
          images={viewer.images}
          onClose={closeViewer}
          t={t} tr={tr}
        />
      )}

      {/* ── Header ── */}
      <div style={{
        borderBottom: `1px solid ${t.border}`,
        background: t.bgHeader, padding: "0 24px",
        position: "sticky", top: 0, zIndex: 100,
        boxShadow: isDark ? "0 1px 12px #00000060" : "0 1px 6px #00000015",
      }}>
        <div style={{ maxWidth: 1700, margin: "0 auto", display: "flex", alignItems: "center", gap: 12, height: 56 }}>

          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: "linear-gradient(135deg,#0ea5e9,#6366f1)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 16, fontWeight: 700, color: "#fff",
            }}>A</div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: t.text, fontFamily: "'IBM Plex Sans'" }}>AOI Tool</div>
              <div style={{ fontSize: 10, color: t.textMuted }}>{tr.appSub}</div>
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display: "flex", gap: 2, marginLeft: 16 }}>
            {[["inspection", tr.tabInspection], ["search", tr.tabSearch]].map(([key, label]) => (
              <button key={key} onClick={() => setTab(key)} style={{
                padding: "6px 16px", borderRadius: 6, border: "none", cursor: "pointer",
                fontFamily: "'IBM Plex Sans'", fontSize: 13, fontWeight: 600,
                background: tab === key ? t.tabActive.bg    : t.tabInactive.bg,
                color:      tab === key ? t.tabActive.color : t.tabInactive.color,
              }}>{label}</button>
            ))}
          </div>

          <div style={{ flex: 1 }} />

          <button
            onClick={() => setIdeasOpen(true)}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "5px 12px", borderRadius: 8,
              border: `1px solid ${t.border}`, background: "transparent",
              color: t.textMuted, fontSize: 12,
              fontFamily: "'IBM Plex Sans'", fontWeight: 600,
              cursor: "pointer", transition: "all 0.15s",
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "#22c55e"; e.currentTarget.style.color = "#22c55e"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = t.border; e.currentTarget.style.color = t.textMuted; }}
          >
            💡 Ideas
          </button>

          <SyncBar t={t} tr={tr} />
          {lastTime && (
            <span style={{ fontSize: 11, color: t.textMuted }}>
              {lastTime}{duration > 0 ? ` (${duration}s)` : ""}
            </span>
          )}

          <LangToggle lang={lang} setLang={setLang} t={t} />

          {/* Live / Test */}
          <div style={{
            display: "flex", alignItems: "center",
            borderRadius: 20, overflow: "hidden",
            border: `1px solid ${appMode === "test" ? "#f97316" : t.border}`,
            opacity: modeLoading ? 0.6 : 1,
          }}>
            {[["live", tr.modeLive], ["test", tr.modeTest]].map(([mode, label]) => {
              const isActive = appMode === mode;
              const isTest   = mode === "test";
              return (
                <button key={mode} onClick={() => switchMode(mode)} disabled={modeLoading} style={{
                  padding: "5px 13px", border: "none",
                  cursor: modeLoading ? "not-allowed" : "pointer",
                  fontFamily: "'IBM Plex Sans'", fontSize: 12, fontWeight: 700,
                  background: isActive ? (isTest ? "#431900" : "#052e16") : "transparent",
                  color:      isActive ? (isTest ? "#fb923c" : "#4ade80") : t.textMuted,
                  display: "flex", alignItems: "center", gap: 5,
                }}>
                  {isActive && (
                    <span style={{
                      width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                      background: isTest ? "#f97316" : "#22c55e",
                      boxShadow: `0 0 6px ${isTest ? "#f97316" : "#22c55e"}`,
                    }} />
                  )}
                  {label}
                </button>
              );
            })}
            {ideasOpen && <IdeasPanel t={t} tr={tr} onClose={() => setIdeasOpen(false)} />}
          </div>

          {/* Dark / Light */}
          <button onClick={() => setIsDark(d => !d)} style={{
            width: 36, height: 36, borderRadius: 8,
            border: `1px solid ${t.border}`, background: "transparent",
            color: t.textSub, fontSize: 16, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>{t.toggleIcon}</button>
        </div>
      </div>

      {/* ── Content ── */}
      <div style={{ maxWidth: 1700, margin: "0 auto", padding: "16px 24px" }}>

        {tab === "search" && <SearchPmTab t={t} tr={tr} />}

        {tab === "inspection" && (
          <>
            <InspectionPanel
              inspMode={inspMode}
              setInspMode={setInspMode}
              loading={loading}
              progressMsg={progressMsg}
              onRun={runInspection}
              t={t} tr={tr}
            />

            <InspectionTable
              currentData={currentData}
              loading={loading}
              error={error}
              inspMode={inspMode}
              t={t} tr={tr}
              onOpenViewer={openViewer}
            />
          </>
        )}
      </div>
    </div>
  );
}
