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
import { AuthProvider, useAuth } from "./components/AuthContext.jsx";
import { Login, ChangePassword } from "./components/Login.jsx";
import { UsersPanel }            from "./components/UsersPanel.jsx";


function AppInner() {
  const { user, loading: authLoading, logout, can } = useAuth();

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

  // Global UI scale (fonts read too small on FullHD at 100%). The sidebar
  // height is derived from this so a 100vh column stays exactly one screen tall.
  const ZOOM        = 1.15;
  const SIDEBAR_W   = 232;

  const [ideasOpen, setIdeasOpen] = useState(false);
  const [pwOpen,    setPwOpen]    = useState(false);

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

  // ── Auth gate ───────────────────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
        background: t.bg, color: t.textMuted, fontFamily: "'IBM Plex Sans'",
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: "50%",
          border: `3px solid ${t.border}`, borderTopColor: "#38bdf8",
          animation: "spin 0.8s linear infinite",
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }
  if (!user) return <Login t={t} tr={tr} />;
  if (user.must_change_pw) return <ChangePassword t={t} tr={tr} forced onDone={() => {}} />;

  return (
    <div style={{
      background: t.bg, color: t.text,
      fontFamily: "'IBM Plex Mono','Consolas',monospace",
      transition: "background 0.3s, color 0.3s",
      zoom: ZOOM,   // global scale-up — fonts read too small on FullHD at 100%
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
      {ideasOpen && <IdeasPanel t={t} tr={tr} onClose={() => setIdeasOpen(false)} />}
      {pwOpen && (
        <div style={{ position: "fixed", inset: 0, zIndex: 1000 }}>
          <ChangePassword t={t} tr={tr}
            onCancel={() => setPwOpen(false)}
            onDone={() => setPwOpen(false)} />
        </div>
      )}

      {/* ── App shell: left sidebar + main ── */}
      <div style={{ display: "flex", minHeight: `calc(100vh / ${ZOOM})` }}>

        {/* ════ Sidebar ════ */}
        <aside style={{
          width: SIDEBAR_W, flexShrink: 0,
          position: "sticky", top: 0, alignSelf: "flex-start",
          height: `calc(100vh / ${ZOOM})`, overflowY: "auto",
          background: t.bgHeader,
          borderRight: `1px solid ${t.border}`,
          boxShadow: isDark ? "1px 0 12px #00000060" : "1px 0 6px #00000010",
          display: "flex", flexDirection: "column", gap: 18,
          padding: "16px 14px",
        }}>

          {/* Identity */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 4px" }}>
            <div style={{
              width: 34, height: 34, borderRadius: 9,
              background: "linear-gradient(135deg,#0ea5e9,#6366f1)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 17, fontWeight: 700, color: "#fff", flexShrink: 0,
            }}>A</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: t.text, fontFamily: "'IBM Plex Sans'" }}>AOI Tool</div>
              <div style={{ fontSize: 10, color: t.textMuted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{tr.appSub}</div>
            </div>
          </div>

          {/* Navigation */}
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", color: t.textMuted, textTransform: "uppercase", padding: "0 4px", marginBottom: 2 }}>
              Menu
            </div>
            {[["inspection", tr.tabInspection], ["search", tr.tabSearch],
              ...(can("users.manage") ? [["users", tr.tabUsers]] : [])].map(([key, label]) => {
              const active = tab === key;
              return (
                <button key={key} onClick={() => setTab(key)} style={{
                  display: "flex", alignItems: "center", gap: 8,
                  width: "100%", textAlign: "left",
                  padding: "9px 12px", borderRadius: 8, cursor: "pointer",
                  border: "none", borderLeft: `3px solid ${active ? t.tabActive.color : "transparent"}`,
                  fontFamily: "'IBM Plex Sans'", fontSize: 13, fontWeight: 600,
                  background: active ? t.tabActive.bg : "transparent",
                  color:      active ? t.tabActive.color : t.textMuted,
                }}>
                  {label}
                </button>
              );
            })}
          </div>

          {/* Spacer pushes status + settings to the bottom */}
          <div style={{ flex: 1 }} />

          {/* Live status */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", color: t.textMuted, textTransform: "uppercase", padding: "0 4px" }}>
              Status
            </div>
            <SyncBar t={t} tr={tr} vertical />
            {lastTime && (
              <span style={{ fontSize: 11, color: t.textMuted, padding: "0 4px" }}>
                {lastTime}{duration > 0 ? ` (${duration}s)` : ""}
              </span>
            )}
            {can("ideas.edit") && (
            <button
              onClick={() => setIdeasOpen(true)}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                width: "100%", padding: "7px 12px", borderRadius: 8,
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
            )}
          </div>

          <div style={{ height: 1, background: t.border }} />

          {/* Settings (set-once) */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", color: t.textMuted, textTransform: "uppercase", padding: "0 4px" }}>
              Settings
            </div>

            {/* Language + theme on one row */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <LangToggle lang={lang} setLang={setLang} t={t} />
              <div style={{ flex: 1 }} />
              <button onClick={() => setIsDark(d => !d)} style={{
                width: 34, height: 34, borderRadius: 8, flexShrink: 0,
                border: `1px solid ${t.border}`, background: "transparent",
                color: t.textSub, fontSize: 16, cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>{t.toggleIcon}</button>
            </div>

            {/* Live / Test — full width */}
            {can("mode.switch") && (
            <div style={{
              display: "flex", alignItems: "center", width: "100%",
              borderRadius: 20, overflow: "hidden",
              border: `1px solid ${appMode === "test" ? "#f97316" : t.border}`,
              opacity: modeLoading ? 0.6 : 1,
            }}>
              {[["live", tr.modeLive], ["test", tr.modeTest]].map(([mode, label]) => {
                const isActive = appMode === mode;
                const isTest   = mode === "test";
                return (
                  <button key={mode} onClick={() => switchMode(mode)} disabled={modeLoading} style={{
                    flex: 1, padding: "6px 13px", border: "none",
                    cursor: modeLoading ? "not-allowed" : "pointer",
                    fontFamily: "'IBM Plex Sans'", fontSize: 12, fontWeight: 700,
                    background: isActive ? (isTest ? "#431900" : "#052e16") : "transparent",
                    color:      isActive ? (isTest ? "#fb923c" : "#4ade80") : t.textMuted,
                    display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
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
            </div>
            )}
          </div>

          {/* Account */}
          <div style={{ height: 1, background: t.border }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 4px" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#22c55e", flexShrink: 0,
                             boxShadow: "0 0 6px #22c55e" }} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: t.text,
                              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {user.username}
                </div>
              </div>
              <span style={{
                fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 8, whiteSpace: "nowrap",
                background: t.tabActive.bg, color: t.tabActive.color,
              }}>
                {user.role === "admin" ? tr.roleAdmin
                  : user.role === "aoiteam" ? tr.roleAoiteam : tr.roleVisitor}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => setPwOpen(true)} style={{
                flex: 1, padding: "6px 10px", borderRadius: 8, cursor: "pointer",
                border: `1px solid ${t.border}`, background: "transparent", color: t.textMuted,
                fontSize: 11, fontWeight: 600, fontFamily: "'IBM Plex Sans'",
              }}>{tr.authChangeTitle}</button>
              <button onClick={logout} style={{
                flex: 1, padding: "6px 10px", borderRadius: 8, cursor: "pointer",
                border: `1px solid ${t.rowColors.red.border}55`, background: "transparent",
                color: t.rowColors.red.text, fontSize: 11, fontWeight: 700, fontFamily: "'IBM Plex Sans'",
              }}>{tr.authLogout}</button>
            </div>
          </div>
        </aside>

        {/* ════ Main content ════ */}
        <main style={{ flex: 1, minWidth: 0, overflowX: "hidden" }}>
          <div style={{ maxWidth: 1700, margin: "0 auto", padding: "16px 24px" }}>

            {tab === "search" && <SearchPmTab t={t} tr={tr} />}

            {tab === "users" && can("users.manage") && <UsersPanel t={t} tr={tr} />}

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
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}
