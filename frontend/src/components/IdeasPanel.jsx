// AOI Tool - Ideas Panel
// Slide-in panel from right: submit ideas + view list (role-aware).
//   admin   : sees all, numbers, can mark done / delete
//   aoiteam : sees all, can submit
//   visitor : can submit; sees only their own submissions
import { useState, useEffect, useCallback } from "react";
import * as api from "../api.js";
import { useAuth } from "./AuthContext.jsx";

export function IdeasPanel({ t, tr, onClose }) {
  const { user: me } = useAuth();

  const [ideas,      setIdeas]      = useState([]);
  const [canViewAll, setCanViewAll] = useState(true);
  const [canManage,  setCanManage]  = useState(false);
  const [loading,    setLoading]    = useState(true);
  const [saving,     setSaving]     = useState(false);
  const [error,      setError]      = useState(null);
  const [saveOk,     setSaveOk]     = useState(false);

  // Form state
  const [user,       setUser]       = useState(me?.username || "");
  const [shortDesc,  setShortDesc]  = useState("");
  const [longDesc,   setLongDesc]   = useState("");
  const [formError,  setFormError]  = useState(null);

  useEffect(() => {
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const fetchIdeas = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.fetchIdeas();
      setIdeas(d.ideas || []);
      setCanViewAll(d.can_view_all !== false);
      setCanManage(!!d.can_manage);
      setError(null);
    } catch (e) {
      setError("Could not load ideas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchIdeas(); }, [fetchIdeas]);

  const handleSubmit = async () => {
    if (!user.trim())      { setFormError("Your name is required."); return; }
    if (!shortDesc.trim()) { setFormError("Short description is required."); return; }
    setFormError(null);
    setSaving(true);
    try {
      await api.addIdea({ user, short_desc: shortDesc, long_desc: longDesc });
      setShortDesc(""); setLongDesc("");
      setSaveOk(true);
      setTimeout(() => setSaveOk(false), 2500);
      await fetchIdeas();
    } catch (e) {
      setFormError("Could not save idea. Try again.");
    } finally {
      setSaving(false);
    }
  };

  const toggleDone = async (idea) => {
    try { await api.setIdeaDone(idea.nr, !idea.done); await fetchIdeas(); }
    catch (e) { setError(e.message); }
  };
  const removeIdea = async (idea) => {
    if (!window.confirm(`Delete idea #${idea.nr}?`)) return;
    try { await api.deleteIdea(idea.nr); await fetchIdeas(); }
    catch (e) { setError(e.message); }
  };

  const inputStyle = {
    width: "100%", padding: "8px 12px", borderRadius: 8,
    border: `1px solid ${t.borderInput}`,
    background: t.bgInput, color: t.text,
    fontFamily: "'IBM Plex Sans'", fontSize: 13,
    outline: "none", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", fontSize: 10, fontWeight: 700,
    letterSpacing: "0.08em", color: t.textMuted,
    textTransform: "uppercase", marginBottom: 5,
  };

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, zIndex: 900,
        background: "rgba(0,0,0,0.45)", animation: "fadeIn 0.2s ease",
      }} />

      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: 560, zIndex: 901, background: t.bgHeader,
        borderLeft: `2px solid ${t.border}`,
        display: "flex", flexDirection: "column",
        boxShadow: "-8px 0 32px rgba(0,0,0,0.35)",
        animation: "slideInRight 0.25s ease",
      }}>

        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "14px 20px", borderBottom: `1px solid ${t.border}`, flexShrink: 0,
        }}>
          <span style={{ fontSize: 20 }}>💡</span>
          <span style={{ fontFamily: "'IBM Plex Sans'", fontWeight: 700, fontSize: 16, color: t.text, flex: 1 }}>
            Improvement Ideas
          </span>
          <button onClick={onClose} style={{
            width: 32, height: 32, borderRadius: 8,
            border: `1px solid ${t.border}`, background: "transparent",
            color: t.textMuted, fontSize: 16, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>✕</button>
        </div>

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>

          {/* ── Add form ── */}
          <div style={{
            borderRadius: 10, border: `1px solid ${t.border}`,
            padding: "16px 18px", marginBottom: 24, background: t.bg,
          }}>
            <div style={{
              fontFamily: "'IBM Plex Sans'", fontWeight: 700, fontSize: 13,
              color: t.tabActive.color, marginBottom: 14,
            }}>+ Add new idea</div>

            <div style={{ marginBottom: 12 }}>
              <label style={labelStyle}>Your name</label>
              <input value={user}
                onChange={e => { setUser(e.target.value); setFormError(null); }}
                placeholder="John Doe" style={inputStyle} />
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={labelStyle}>Short description</label>
              <input value={shortDesc}
                onChange={e => { setShortDesc(e.target.value); setFormError(null); }}
                placeholder="One line summary" style={inputStyle} />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Long description <span style={{ color: t.border }}>(optional)</span></label>
              <textarea value={longDesc}
                onChange={e => setLongDesc(e.target.value)}
                placeholder="Detailed explanation, steps, expected benefit..."
                rows={4} style={{ ...inputStyle, resize: "vertical", lineHeight: 1.6 }} />
            </div>

            {formError && <div style={{ fontSize: 12, color: "#ef4444", marginBottom: 10 }}>⚠ {formError}</div>}
            {saveOk    && <div style={{ fontSize: 12, color: "#22c55e", marginBottom: 10 }}>✓ Idea saved!</div>}

            <button onClick={handleSubmit} disabled={saving} style={{
              padding: "8px 20px", borderRadius: 8, border: "none",
              background: saving ? t.border : "linear-gradient(135deg,#0ea5e9,#6366f1)",
              color: saving ? t.textMuted : "#fff",
              fontFamily: "'IBM Plex Sans'", fontSize: 13, fontWeight: 600,
              cursor: saving ? "not-allowed" : "pointer",
              display: "flex", alignItems: "center", gap: 6,
            }}>
              {saving
                ? <><span style={{ animation: "spin 0.8s linear infinite", display: "inline-block" }}>⟳</span> Saving...</>
                : "💾 Save idea"}
            </button>
          </div>

          {/* ── Ideas list ── */}
          <div>
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: "0.1em",
              color: t.textMuted, textTransform: "uppercase", marginBottom: 4,
            }}>
              {canViewAll ? `Existing ideas (${ideas.length})` : `Your submissions (${ideas.length})`}
            </div>
            {!canViewAll && (
              <div style={{ fontSize: 11, color: t.textMuted, marginBottom: 12 }}>
                You can submit ideas; only your own are shown here.
              </div>
            )}
            {canViewAll && <div style={{ marginBottom: 12 }} />}

            {loading && (
              <div style={{ color: t.textMuted, fontSize: 13, textAlign: "center", padding: 20 }}>Loading...</div>
            )}
            {!loading && error && <div style={{ color: "#ef4444", fontSize: 13 }}>⚠ {error}</div>}
            {!loading && !error && ideas.length === 0 && (
              <div style={{ color: t.textMuted, fontSize: 13, textAlign: "center", padding: 20 }}>
                {canViewAll ? "No ideas yet. Be the first!" : "Your submitted ideas will appear here."}
              </div>
            )}

            {!loading && ideas.map((idea) => {
              const done = !!idea.done;
              return (
                <div key={idea.nr ?? idea.id} style={{
                  borderRadius: 8,
                  border: `1px solid ${done ? `${t.rowColors.green.border}66` : t.border}`,
                  padding: "12px 16px", marginBottom: 10,
                  background: done ? t.rowColors.green.bg : t.bgTable,
                  opacity: done ? 0.85 : 1,
                }}>
                  {/* Meta row */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <span style={{
                      padding: "2px 7px", borderRadius: 8, fontSize: 11, fontWeight: 700,
                      fontFamily: "monospace", background: t.cliChip.bg, color: t.cliChip.color,
                    }}>#{idea.nr}</span>
                    <span style={{
                      padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 600,
                      fontFamily: "monospace", background: t.tabActive.bg, color: t.tabActive.color,
                    }}>{idea.user}</span>
                    {done && (
                      <span style={{
                        padding: "2px 8px", borderRadius: 10, fontSize: 10, fontWeight: 700,
                        background: t.rowColors.green.bg, color: t.rowColors.green.text,
                        border: `1px solid ${t.rowColors.green.border}66`,
                      }}>✓ DONE</span>
                    )}
                    <span style={{ fontSize: 11, color: t.textMuted, marginLeft: "auto" }}>{idea.added_at}</span>
                  </div>

                  {/* Short desc */}
                  <div style={{
                    fontFamily: "'IBM Plex Sans'", fontWeight: 600, fontSize: 14,
                    color: t.text, marginBottom: idea.long_desc ? 6 : 0,
                    textDecoration: done ? "line-through" : "none",
                  }}>
                    {idea.short_desc}
                  </div>

                  {/* Long desc */}
                  {idea.long_desc && (
                    <div style={{ fontSize: 12, color: t.textSub, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                      {idea.long_desc}
                    </div>
                  )}

                  {/* Admin controls */}
                  {canManage && (
                    <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                      <button onClick={() => toggleDone(idea)} style={{
                        padding: "5px 11px", borderRadius: 8, cursor: "pointer", fontSize: 11, fontWeight: 700,
                        fontFamily: "'IBM Plex Sans'",
                        border: `1px solid ${done ? t.border : `${t.rowColors.green.border}88`}`,
                        background: "transparent",
                        color: done ? t.textMuted : t.rowColors.green.text,
                      }}>{done ? "↺ Reopen" : "✓ Mark done"}</button>
                      <button onClick={() => removeIdea(idea)} style={{
                        padding: "5px 11px", borderRadius: 8, cursor: "pointer", fontSize: 11, fontWeight: 700,
                        fontFamily: "'IBM Plex Sans'",
                        border: `1px solid ${t.rowColors.red.border}55`, background: "transparent",
                        color: t.rowColors.red.text,
                      }}>🗑 Delete</button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: "10px 20px", borderTop: `1px solid ${t.border}`,
          fontSize: 10, color: t.textMuted, textAlign: "center", flexShrink: 0,
        }}>
          ESC or click outside to close
        </div>
      </div>

      <style>{`
        @keyframes fadeIn       { from { opacity: 0 }                  to { opacity: 1 }            }
        @keyframes slideInRight { from { transform: translateX(100%) } to { transform: translateX(0) } }
      `}</style>
    </>
  );
}
